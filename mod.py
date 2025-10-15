import os
from datetime import datetime, timedelta

from dateutil import parser
from sqlalchemy import (
    Boolean,
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
    desc,
    event,
    func,
    select,
    text,
)
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import sqltypes

from . import Base


class BaseModel(Base):
    __abstract__ = True
    #  Used by alembic to generate revisions with the right schema.
    __table_args__ = {"schema": os.environ["DATABASE_SCHEMA"]}

    def __init__(self, **kwargs):
        cls = type(self)

        for key, value in kwargs.items():
            # Ignore named parameters that are not defined in the model
            if key not in cls.__table__.columns:
                continue

            # Cast Date and DateTime values
            if value is not None and isinstance(value, str):
                if type(cls.__table__.columns[key].type) is sqltypes.Date:
                    value = parser.parse(value).date()
                elif type(cls.__table__.columns[key].type) is DATETIME2:
                    value = parser.parse(value)

            setattr(self, key, value)


class Metadata(BaseModel):
    __tablename__ = "metadata"

    id = Column(Integer, primary_key=True, autoincrement=True)
    is_db_locked = Column(Boolean)
    quotes_updated_at_dtm = Column(DATETIME2)


class User(BaseModel):
    __tablename__ = "users"

    id = Column(String(20), primary_key=True)

    first_name = Column(String)
    last_name = Column(String)
    email = Column(String)

    requested_at_dtm = Column(DATETIME2)
    created_at_dtm = Column(DATETIME2, server_default=func.now())

    roles = relationship("UserRole", primaryjoin="User.id==UserRole.user_id")

    @validates("id")
    def convert_upper(self, key, value):
        return value.upper() if value is not None else value


class UserRole(BaseModel):
    __tablename__ = "user_roles"

    user_id = Column(String(20), ForeignKey(User.id), primary_key=True)
    role = Column(String(20), primary_key=True)


class Quote(BaseModel):
    __tablename__ = "quotes"

    quote_number = Column(String(20), primary_key=True)
    policy_number = Column(String)
    quote_entry_date = Column(
        DATETIME2
    )  # created_at_dtm: ordering (assignation & next-quote)
    account_number = Column(String)
    product = Column(String)
    business_name = Column(String)
    phone_number = Column(String)
    pol_jurisdiction_de = Column(String)
    last_contacted_advisor = Column(String)
    last_contacted_advisor_id = Column(String(20), index=True)
    create_contacted_advisor = Column(String)
    create_contacted_advisor_id = Column(String(20))
    transaction_status = Column(String(50), index=True)
    pol_effective_date = Column(DATETIME2)
    last_entry_date = Column(
        DATETIME2, index=True
    )  # updated_at_dtm: expiring after 10 days
    quote_channel = Column(String(50), index=True)
    current_premium = Column(Float)
    web_phone_in = Column(Integer)
    reject_reason = Column(String(50), index=True)
    sqpm_quote_sale_reporting_in = Column(Integer, index=True)

    advisor = relationship(
        "User",
        primaryjoin="Quote.last_contacted_advisor_id==User.id",
        uselist=False,
        backref="quotes",
        foreign_keys=last_contacted_advisor_id,
    )

    create_advisor = relationship(
        "User",
        primaryjoin="Quote.create_contacted_advisor_id==User.id",
        uselist=False,
        backref="quotes_created",
        foreign_keys=create_contacted_advisor_id,
    )

    @hybrid_property
    def latest_scheduled_outbound_dt(self):
        if self.outbounds:
            scheduled_dates = [
                ob.scheduled_outbound_dt
                for ob in self.outbounds
                if ob.scheduled_outbound_dt
            ]
            return max(scheduled_dates) if scheduled_dates else None
        return None

    @latest_scheduled_outbound_dt.expression
    def latest_scheduled_outbound_dt(cls):
        return (
            select(func.max(Outbound.scheduled_outbound_dt))
            .where(Outbound.quote_number == cls.quote_number)
            .scalar_subquery()
        )

    @hybrid_property
    def expiry_dt(self):
        dates = []
        if self.last_entry_date:
            dates.append(self.last_entry_date + timedelta(days=10))
        if self.latest_scheduled_outbound_dt:
            dates.append(self.latest_scheduled_outbound_dt + timedelta(days=10))
        return max(dates) if dates else None

    @expiry_dt.expression
    def expiry_dt(cls):
        return func.dateadd(
            text("day"),
            10,
            func.coalesce(
                func.greatest(
                    cls.last_entry_date,
                    cls.latest_scheduled_outbound_dt,
                ),
                cls.last_entry_date,
            ),
        )

    @hybrid_property
    def latest_result(self):
        if self.outbounds:
            completed_outbounds = [ob for ob in self.outbounds if ob.completed_at_dtm]
            if completed_outbounds:
                latest = max(completed_outbounds, key=lambda x: x.completed_at_dtm)
                return latest.result or ""
        return ""

    @latest_result.expression
    def latest_result(cls):
        latest_completed_outbound = (
            select(Outbound.result)
            .where(Outbound.quote_number == cls.quote_number)
            .where(Outbound.completed_at_dtm.isnot(None))
            .order_by(desc(Outbound.completed_at_dtm))
            .limit(1)
            .scalar_subquery()
        )
        return func.coalesce(latest_completed_outbound, "")

    @validates("last_contacted_advisor_id", "create_contacted_advisor_id")
    def convert_upper(self, key, value):
        return value.upper() if value is not None else value


class QuoteHistory(BaseModel):
    __tablename__ = "quotes_history"

    quote_number = Column(String(20), primary_key=True)
    policy_number = Column(String)
    quote_entry_date = Column(DATETIME2)
    account_number = Column(String)
    product = Column(String)
    business_name = Column(String)
    phone_number = Column(String)
    pol_jurisdiction_de = Column(String)
    last_contacted_advisor = Column(String)
    last_contacted_advisor_id = Column(String(20))
    create_contacted_advisor = Column(String)
    create_contacted_advisor_id = Column(String(20))
    transaction_status = Column(String)
    pol_effective_date = Column(DATETIME2)
    last_entry_date = Column(DATETIME2, primary_key=True)
    quote_channel = Column(String)
    current_premium = Column(Float)
    web_phone_in = Column(Integer)
    reject_reason = Column(String)
    sqpm_quote_sale_reporting_in = Column(Integer)


class Outbound(BaseModel):
    __tablename__ = "outbounds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    quote_number = Column(String(20), index=True)

    user_id = Column(String(20))
    assigned_by = Column(String(20))
    unassigned_by = Column(String(20))

    result = Column(String)
    is_inbound = Column(Boolean)
    scheduled_outbound_dt = Column(DATETIME2)
    comment = Column(String)

    assigned_at_dtm = Column(DATETIME2, server_default=func.now())
    started_at_dtm = Column(DATETIME2)
    completed_at_dtm = Column(DATETIME2, index=True)
    unassigned_at_dtm = Column(DATETIME2, index=True)

    created_at_dtm = Column(DATETIME2, server_default=func.now())

    quote = relationship(
        "Quote",
        primaryjoin="Outbound.quote_number==Quote.quote_number",
        uselist=False,
        backref="outbounds",
        foreign_keys=quote_number,
    )
    advisor = relationship(
        "User",
        primaryjoin="Outbound.user_id==User.id",
        uselist=False,
        backref="advisor_outbounds",
        foreign_keys=user_id,
    )
    assigner = relationship(
        "User",
        primaryjoin="Outbound.assigned_by==User.id",
        uselist=False,
        backref="assigner_outbounds",
        foreign_keys=assigned_by,
    )


@event.listens_for(Outbound, "before_insert")
def before_outbound_store(mapper, connection, target):
    assigned_at_dtm = connection.scalar(
        select(Outbound.assigned_at_dtm)
        .where(Outbound.quote_number == target.quote_number)
        .order_by(desc(Outbound.created_at_dtm))
    )

    if (
        target.assigned_at_dtm is None
        and assigned_at_dtm is not None
        and assigned_at_dtm > datetime.utcnow()
    ):
        target.assigned_at_dtm = assigned_at_dtm


class RepData(BaseModel):
    __tablename__ = "repdata"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date_type = Column(String, nullable=False)
    date_value = Column(DATETIME2, nullable=False)
    product = Column(String, nullable=False)
    quote_channel = Column(String, nullable=False)
    quote_count = Column(Integer, nullable=False)
    sale_count = Column(Integer, nullable=False)
    sum_attempts = Column(Integer, nullable=False)
    new_leads_given = Column(Integer, nullable=False)
    new_leads_contacted = Column(Integer, nullable=False)
    leads_no_recontact_needed = Column(Integer, nullable=False)


class AttemptDetails(BaseModel):
    __tablename__ = "attempt_details"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date_type = Column(String, nullable=False)
    date_value = Column(DATETIME2, nullable=False)
    product = Column(String, nullable=False)
    quote_channel = Column(String, nullable=False)
    series_name = Column(String, nullable=False)
    series_value = Column(Integer, nullable=False)
