from sqlalchemy import case, distinct, text, cast, Integer, literal_column, Table, Column, String, func, inspect, union_all, select, or_
from sqlalchemy.orm import Session

inspector = inspect(engine)

def create_date_aggregation(cte, date_column, date_type_literal):
    """
    Helper function to create date-based aggregation queries.
    Reduces code duplication for week/month/year aggregations.
    
    Args:
        cte: The CTE to aggregate from
        date_column: The column to use for date grouping (e.g., c.week_end_date)
        date_type_literal: The literal value for date_type (e.g., 'week', 'month', 'year')
    """
    return select(
        literal_column(f"'{date_type_literal}'").label("date_type"),
        date_column.label("date_value"),
        cte.c.product.label("product"),
        cte.c.quote_channel.label("quote_channel"),
        func.sum(case((cte.c.result == "Sale - Policy", 1), else_=0)).label("sale_count"),
        func.count(cte.c.quote_number).label("quote_count"),
        func.sum(cte.c.attempt_ind).label("sum_attempts"),
        func.sum(case((cte.c.new_ind == 1, 1), else_=0)).label("new_leads_given"),
        func.sum(case((cte.c.new_ind == 1, cte.c.attempt_ind), else_=0)).label("new_leads_contacted"),
        func.sum(case((cte.c.result == "Sale - No recontact", 1), else_=0)).label("leads_no_recontact_needed"),
        func.sum(case((cte.c.result == "Answering Machine - No Message", 1), else_=0)).label("ta_answering_machine_no_message"),
        func.sum(case((cte.c.result == "Sale - Policy", 1), else_=0)).label("ta_sale_policy"),
        func.sum(case((cte.c.result == "Call back scheduled", 1), else_=0)).label("ta_call_back_scheduled"),
        func.sum(case((cte.c.result == "Too Expensive", 1), else_=0)).label("ta_too_expensive"),
        func.sum(case((cte.c.result == "Inbound - extension", 1), else_=0)).label("ta_inbound_extension"),
        func.sum(case((cte.c.result == "No Reason Provided", 1), else_=0)).label("ta_no_reason_provided"),
        func.sum(case((cte.c.result == "Purchased insurance elsewhere", 1), else_=0)).label("ta_purchased_insurance_elsewhere"),
        func.sum(case((cte.c.result == "No Product Need", 1), else_=0)).label("ta_no_product_need"),
        func.sum(case((cte.c.result == "Bad phone number", 1), else_=0)).label("ta_bad_phone_number"),
        func.sum(case((cte.c.result == "Customer Policy not up for renewal", 1), else_=0)).label("ta_customer_policy_not_up_for_renewal"),
        func.sum(case((cte.c.result == "Customer satisfied with current insurer", 1), else_=0)).label("ta_customer_satisfied_with_current_insurer"),
        func.sum(case((cte.c.result == "Declined by Insurer for other reason", 1), else_=0)).label("ta_declined_by_insurer_for_other_reason"),
        func.sum(case((cte.c.result == "Active Follow-up Present", 1), else_=0)).label("ta_active_follow_up_present"),
        func.sum(case((cte.c.result == "Other", 1), else_=0)).label("ta_other"),
        func.sum(case((cte.c.result.is_(None), 1), else_=0)).label("ta_none"),
        func.sum(case((cte.c.result == "Total", 1), else_=1)).label("ta_total")
    ).select_from(
        cte
    ).group_by(
        date_column,
        cte.c.product,
        cte.c.quote_channel
    )


with SessionLocal() as db, SessionLocal_ETL() as etl:

    # Step 1: Aggregate Quote data by quote_number to get bound counts
    # Using CTE instead of subquery for better performance
    bound_table = select(
        Quote.quote_number,
        func.sum(case((Quote.transaction_status == "Bound", 1), else_=0)).label("bound_count"),
        func.max(Quote.last_entry_date).label("last_entry_date"), 
        func.max(Quote.product).label("product"),
        func.max(Quote.quote_channel).label("quote_channel")
    ).select_from(
        Quote
    ).group_by(Quote.quote_number).cte('bound_table')

    # Step 2: Join Outbound data with Quote aggregations
    outbound_bound = select(
        *Outbound.__table__.c,
        func.coalesce(bound_table.c.bound_count, 0).label("bound_count"),
        bound_table.c.last_entry_date,
        bound_table.c.product,
        bound_table.c.quote_channel
    ).select_from(
        Outbound
    ).outerjoin(
        bound_table,
        Outbound.quote_number == bound_table.c.quote_number
    ).cte('outbound_bound')

    # Step 3: Add date calculations and filtering
    outbound_non_organic = select(
        outbound_bound,
        func.extract('week', outbound_bound.c.created_at_dtm).label("week_of_year"),
        func.extract('month', outbound_bound.c.created_at_dtm).label("month_of_year"),
        func.extract('year', outbound_bound.c.created_at_dtm).label("year"),
        case(
            (or_(
                outbound_bound.c.scheduled_outbound_dt is None,
                outbound_bound.c.result is None,
                outbound_bound.c.result == "Sale - No recontact"
                ),
            0),
            else_=1
        ).label("attempt_ind"),
        func.dateadd(
            text('day'), 
            cast(func.datediff(text('day'), literal_column("'1900-01-01'"), outbound_bound.c.created_at_dtm) / 7, Integer) * 7 + 4, 
            literal_column("'1900-01-01'")
        ).label("week_end_date"),
        func.dateadd(
            text('day'),
            -1,
            func.dateadd(
                text('month'),
                func.datediff(text('month'), literal_column("'1900-01-01'"), outbound_bound.c.created_at_dtm) + 1,
                literal_column("'1900-01-01'")
            )
        ).label("month_end_date"),
        func.dateadd(
            text('day'),
            -1,
            func.dateadd(
                text('year'),
                func.datediff(text('year'), literal_column("'1900-01-01'"), outbound_bound.c.created_at_dtm) + 1,
                literal_column("'1900-01-01'")
            )
        ).label("year_end_date")
    ).where(
        or_(
            outbound_bound.c.created_at_dtm <= outbound_bound.c.last_entry_date,
            outbound_bound.c.bound_count == 0
        )
    ).cte('outbound_non_organic')

    # Step 4: Add new lead indicator using row_number
    dfw = select(
        outbound_non_organic,
        case(
            (func.row_number().over(
                partition_by=outbound_non_organic.c.quote_number,
                order_by=outbound_non_organic.c.created_at_dtm
            ) == 1, 1), 
            else_=0
        ).label("new_ind")
    ).cte('dfw')

    # Step 5: Create aggregations by week/month/year using helper function
    week_stmt = create_date_aggregation(dfw, dfw.c.week_end_date, 'week')
    month_stmt = create_date_aggregation(dfw, dfw.c.month_end_date, 'month')
    year_stmt = create_date_aggregation(dfw, dfw.c.year_end_date, 'year')

    # Step 6: Union all time periods - using CTE for efficiency since referenced 4 times
    aggregated_stmt = union_all(
        week_stmt,
        month_stmt,
        year_stmt
    ).cte('aggregated')

    # Step 7: Use GROUPING SETS to create all aggregation levels in a single query
    # This replaces the previous 4 separate queries + UNION ALL approach
    # GROUPING SETS generates:
    #   - Per product and channel
    #   - All products (grouped by channel)
    #   - All channels (grouped by product)  
    #   - Grand totals (all products and channels)
    final_stmt = select(
        aggregated_stmt.c.date_type,
        aggregated_stmt.c.date_value,
        func.coalesce(aggregated_stmt.c.product, 'All').label("product"),
        func.coalesce(aggregated_stmt.c.quote_channel, 'All').label("quote_channel"),
        func.sum(aggregated_stmt.c.sale_count).label("sale_count"),
        func.sum(aggregated_stmt.c.quote_count).label("quote_count"),
        func.sum(aggregated_stmt.c.sum_attempts).label("sum_attempts"),
        func.sum(aggregated_stmt.c.new_leads_given).label("new_leads_given"),
        func.sum(aggregated_stmt.c.new_leads_contacted).label("new_leads_contacted"),
        func.sum(aggregated_stmt.c.leads_no_recontact_needed).label("leads_no_recontact_needed"),
        func.sum(aggregated_stmt.c.ta_answering_machine_no_message).label("ta_answering_machine_no_message"),
        func.sum(aggregated_stmt.c.ta_sale_policy).label("ta_sale_policy"),
        func.sum(aggregated_stmt.c.ta_call_back_scheduled).label("ta_call_back_scheduled"),
        func.sum(aggregated_stmt.c.ta_too_expensive).label("ta_too_expensive"),
        func.sum(aggregated_stmt.c.ta_inbound_extension).label("ta_inbound_extension"),
        func.sum(aggregated_stmt.c.ta_no_reason_provided).label("ta_no_reason_provided"),
        func.sum(aggregated_stmt.c.ta_purchased_insurance_elsewhere).label("ta_purchased_insurance_elsewhere"),
        func.sum(aggregated_stmt.c.ta_no_product_need).label("ta_no_product_need"),
        func.sum(aggregated_stmt.c.ta_bad_phone_number).label("ta_bad_phone_number"),
        func.sum(aggregated_stmt.c.ta_customer_policy_not_up_for_renewal).label("ta_customer_policy_not_up_for_renewal"),
        func.sum(aggregated_stmt.c.ta_customer_satisfied_with_current_insurer).label("ta_customer_satisfied_with_current_insurer"),
        func.sum(aggregated_stmt.c.ta_declined_by_insurer_for_other_reason).label("ta_declined_by_insurer_for_other_reason"),
        func.sum(aggregated_stmt.c.ta_active_follow_up_present).label("ta_active_follow_up_present"),
        func.sum(aggregated_stmt.c.ta_other).label("ta_other"),
        func.sum(aggregated_stmt.c.ta_none).label("ta_none"),
        func.sum(aggregated_stmt.c.ta_total).label("ta_total")
    ).select_from(
        aggregated_stmt
    ).group_by(
        text("GROUPING SETS ((date_type, date_value, product, quote_channel), (date_type, date_value, quote_channel), (date_type, date_value, product), (date_type, date_value))")
    ).order_by(
        text('date_type'),
        text('date_value'),
        text('product'),
        text('quote_channel')
    )

    # Step 12: Define the reporting table schema
    repdata = Table(
        "repdata",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("date_type", String),
        Column("date_value", String),
        Column("product", String),
        Column("quote_channel", String),
        Column("sale_count", Integer),
        Column("quote_count", Integer), 
        Column("sum_attempts", Integer),
        Column("new_leads_given", Integer),
        Column("new_leads_contacted", Integer),
        Column("leads_no_recontact_needed", Integer),
        Column("ta_answering_machine_no_message", Integer),
        Column("ta_sale_policy", Integer),
        Column("ta_call_back_scheduled", Integer),
        Column("ta_too_expensive", Integer),
        Column("ta_inbound_extension", Integer),
        Column("ta_no_reason_provided", Integer),
        Column("ta_purchased_insurance_elsewhere", Integer),
        Column("ta_no_product_need", Integer),
        Column("ta_bad_phone_number", Integer),
        Column("ta_customer_policy_not_up_for_renewal", Integer),
        Column("ta_customer_satisfied_with_current_insurer", Integer),
        Column("ta_declined_by_insurer_for_other_reason", Integer),
        Column("ta_active_follow_up_present", Integer),
        Column("ta_other", Integer),
        Column("ta_none", Integer),
        Column("ta_total", Integer),
        extend_existing=True
    )

    # Step 13: Prepare table for new data
    if inspector.has_table("repdata"):
        print("Table repdata exists, deleting all rows...")
        db.execute(repdata.delete())
        db.commit()
    else:
        print("Table repdata does not exist, creating it...")
        repdata.create(bind=engine)

    # Step 14: Execute query and bulk insert results
    print("Executing query and loading results...")
    result = db.execute(final_stmt)
    
    # Convert results to list of dictionaries for bulk insert
    rows_to_insert = [row._mapping for row in result]
    
    # Bulk insert all rows at once - much more efficient than row-by-row
    if rows_to_insert:
        db.execute(repdata.insert(), rows_to_insert)
        db.commit()
        print(f"Successfully loaded {len(rows_to_insert)} rows into repdata")
    else:
        print("No rows to insert")

    # Step 15: Verify results
    result_count = db.execute(select(func.count()).select_from(repdata)).scalar()
    print(f"Total rows in repdata: {result_count}")
    
    # Show sample row
    sample = db.execute(select(repdata).limit(1)).first()
    if sample:
        print(f"Sample row - Date: {sample.date_value}, Product: {sample.product}, Channel: {sample.quote_channel}")
    
    print("Done")
