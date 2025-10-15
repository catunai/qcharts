from datetime import date, datetime, timedelta
from typing import List, Union

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import and_, case, desc, func, or_, select

from src import serializers, validators
from src.database import dbutils, models
from src.validators.api import quotes as QuoteValidator

router = APIRouter(prefix="/quotes")


@router.get("", response_model=serializers.pagination_factory(serializers.Quote))
def index(
    request: Request,
    query: dict = Depends(QuoteValidator.index_query),
):
    stmt = select(models.Quote)

    if query["filters"]["self_assigned"] is not None:
        latest_outbounds_subquery = (
            select(
                models.Outbound.quote_number, func.max(models.Outbound.created_at_dtm)
            )
            .where(
                and_(
                    models.Outbound.user_id == request.state.auth["user"].id,
                    models.Outbound.completed_at_dtm.is_(None),
                    models.Outbound.unassigned_at_dtm.is_(None),
                )
            )
            .group_by(models.Outbound.quote_number)
            .subquery()
        )

        stmt = stmt.where(
            or_(
                models.Quote.last_entry_date > (datetime.utcnow() - timedelta(days=10)),
                models.Quote.quote_number.in_(
                    select(models.Outbound.quote_number).where(
                        models.Outbound.scheduled_outbound_dt
                        > (datetime.utcnow() - timedelta(days=10))
                    )
                ),
            ),
        )

        stmt = stmt.join(
            latest_outbounds_subquery,
            models.Quote.quote_number == latest_outbounds_subquery.c.quote_number,
        )

    else:
        if not any(role in ["ADMIN", "TM"] for role in request.state.auth["roles"]):
            raise HTTPException(status_code=403)
        """
            Actionable Quotes
        """
        stmt = stmt.where(
            and_(
                models.Quote.transaction_status.in_(["Quoted", "Draft", "Quoting"]),
                models.Quote.quote_channel.in_(["Web", "Inbound"]),
                models.Quote.reject_reason.is_(None),
                models.Quote.sqpm_quote_sale_reporting_in == 1,
                or_(
                    models.Quote.last_entry_date
                    > (datetime.utcnow() - timedelta(days=10)),
                    models.Quote.quote_number.in_(
                        select(models.Outbound.quote_number).where(
                            models.Outbound.scheduled_outbound_dt
                            > (datetime.utcnow() - timedelta(days=10))
                        )
                    ),
                ),
            )
        )

    for filter in [
        _filter for _filter in query["filters"] if _filter != "self_assigned"
    ]:
        if filter == "assigned_to" and query["filters"][filter] is not None:
            latest_outbounds_subquery = (
                select(
                    models.Outbound.quote_number,
                    func.max(models.Outbound.created_at_dtm),
                )
                .where(
                    and_(
                        models.Outbound.completed_at_dtm.is_(None),
                        models.Outbound.unassigned_at_dtm.is_(None),
                        models.Outbound.advisor.has(
                            (
                                models.User.first_name + " " + models.User.last_name
                            ).ilike(f"%{query['filters'][filter]}%")
                        ),
                    )
                )
                .group_by(models.Outbound.quote_number)
                .subquery()
            )

            stmt = stmt.join(
                latest_outbounds_subquery,
                models.Quote.quote_number == latest_outbounds_subquery.c.quote_number,
            )
        elif filter == "expiring_in":
            if query["filters"].get(filter):
                days_num = float(query["filters"][filter])
                stmt = stmt.where(
                    models.Quote.expiry_dt
                    <= (datetime.utcnow() + timedelta(days=days_num))
                )
        elif filter == "latest_result":
            if query["filters"][filter] is not None:
                if query["filters"][filter] == "<Blank>":
                    stmt = stmt.where(models.Quote.latest_result == "")
                elif query["filters"][filter] != "":
                    stmt = stmt.where(
                        models.Quote.latest_result == query["filters"][filter]
                    )
        else:
            if query["filters"][filter] is not None:
                if isinstance(query["filters"][filter], List):
                    stmt = stmt.where(
                        or_(
                            *[
                                getattr(models.Quote, filter, None).ilike(f"%{item}%")
                                for item in query["filters"][filter]
                            ]
                        )
                    )
                else:
                    stmt = stmt.where(
                        getattr(models.Quote, filter, None).ilike(
                            f"%{query['filters'][filter]}%"
                        )
                    )

    orderby = ()

    if query["sorting"]["value"] is not None:
        if query["sorting"]["value"].value == "pending":
            order = case(
                (
                    models.Quote.outbounds.any(
                        and_(
                            models.Outbound.assigned_at_dtm > datetime.utcnow(),
                            models.Outbound.completed_at_dtm.is_(None),
                            models.Outbound.unassigned_at_dtm.is_(None),
                        )
                    ),
                    1,
                ),
                else_=0,
            )
            if query["sorting"]["direction"] == validators.SortingDirections.asc:
                orderby = (order,)
            else:
                orderby = (desc(order),)
        elif query["sorting"]["value"].value == "expiring_in":
            if query["sorting"]["direction"] == validators.SortingDirections.asc:
                orderby = (models.Quote.expiry_dt,)
            else:
                orderby = (desc(models.Quote.expiry_dt),)
        elif query["sorting"]["value"].value == "latest_result":
            if query["sorting"]["direction"] == validators.SortingDirections.asc:
                orderby = (models.Quote.latest_result,)
            else:
                orderby = (desc(models.Quote.latest_result),)
        else:
            if query["sorting"]["direction"] == validators.SortingDirections.asc:
                orderby = (query["sorting"]["value"].value,)
            else:
                orderby = (desc(query["sorting"]["value"].value),)
    else:
        orderby = (models.Quote.quote_number,)

    return dbutils.paginate(request.state.db, stmt, orderby, **query["pagination"])


@router.get("/export", response_model=List[serializers.QuoteHistory])
def export_quotes(
    request: Request,
    start: Union[date, None] = None,
    end: Union[date, None] = None,
):
    if "ADMIN" not in request.state.auth["roles"]:
        raise HTTPException(status_code=403)

    quotes_stmt = select(models.QuoteHistory).order_by(
        models.QuoteHistory.quote_number,
        desc(models.QuoteHistory.quote_entry_date),
    )

    if start is not None:
        # convert the date to the start of the day datetime
        start = datetime.combine(start, datetime.min.time())

        # filter the quotes
        quotes_stmt = quotes_stmt.where(models.QuoteHistory.quote_entry_date >= start)

    if end is not None:
        # convert the date to the end of the day datetime
        end = datetime.combine(end, datetime.max.time())

        # filter the quotes
        quotes_stmt = quotes_stmt.where(models.QuoteHistory.quote_entry_date <= end)

    return request.state.db.scalars(quotes_stmt).all()


@router.get("/report_data", response_model=List[serializers.RepData])
def report_data(
    request: Request,
    channel: str,
    product: str,
    date_type: str,
):
    if "ADMIN" not in request.state.auth["roles"]:
        raise HTTPException(status_code=403)

    report_stmt = select(models.RepData).where(
        and_(
            models.RepData.quote_channel == channel,
            models.RepData.product == product,
            models.RepData.date_type == date_type,
        )
    )

    return request.state.db.scalars(report_stmt).all()


@router.get("/report_data_melted", response_model=List[serializers.MeltedAttemptData])
def report_data_melted(
    request: Request,
    channel: str,
    product: str,
    date_type: str,
):
    if "ADMIN" not in request.state.auth["roles"]:
        raise HTTPException(status_code=403)

    report_stmt = select(models.RepData).where(
        and_(
            models.RepData.quote_channel == channel,
            models.RepData.product == product,
            models.RepData.date_type == date_type,
        )
    )

    report_data = request.state.db.scalars(report_stmt).all()

    # Melt the data: transform wide format to long format
    melted_data = []
    
    # Define the mapping of column names to series names
    series_mapping = {
        'ta_answering_machine_no_message': 'Answering Machine - No Message',
        'ta_sale_policy': 'Sale - Policy',
        'ta_call_back_scheduled': 'Call back scheduled',
        'ta_too_expensive': 'Too expensive',
        'ta_inbound_extension': 'Inbound - extension',
        'ta_no_reason_provided': 'No Reason Provided',
        'ta_purchased_insurance_elsewhere': 'Purchased insurance elsewhere',
        'ta_no_product_need': 'No Product Need',
        'ta_bad_phone_number': 'Bad phone number',
        'ta_customer_policy_not_up_for_renewal': 'Customer Policy not up for renewal',
        'ta_customer_satisfied_with_current_insurer': 'Customer satisfied with current insurer',
        'ta_declined_by_insurer_for_other_reason': 'Declined by Insurer for other reason',
        'ta_active_follow_up_present': 'Active Follow-up Present',
        'ta_other': 'Other',
        'ta_none': 'None',
        'ta_total': 'Total'
    }
    
    for row in report_data:
        for column_name, series_name in series_mapping.items():
            value = getattr(row, column_name, 0)
            melted_data.append(
                serializers.MeltedAttemptData(
                    date_value=row.date_value,
                    series_name=series_name,
                    series_value=value if value is not None else 0
                )
            )
    
    return melted_data


@router.get("/{quote_number}", response_model=serializers.Quote)
def show(quote_number, request: Request):
    quote = request.state.db.scalar(
        select(models.Quote).where(models.Quote.quote_number == quote_number)
    )

    if quote is None:
        raise HTTPException(status_code=404)

    return quote
