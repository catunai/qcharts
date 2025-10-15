from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, create_model, field_serializer


class BaseSerializer(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def pagination_factory(Model):
    class PaginationSerializer(BaseSerializer):
        page: int
        limit: int
        total: int
        data: List[Model]

    return create_model(
        __model_name=f"{Model.__name__}Pagination", __base__=PaginationSerializer
    )


class Metadata(BaseSerializer):
    quotes_updated_at_dtm: Optional[datetime]

    @field_serializer("quotes_updated_at_dtm")
    def serialize_quotes_updated_at_dtm(self, quotes_updated_at_dtm: datetime, _info):
        return (
            quotes_updated_at_dtm.strftime("%Y-%m-%d %H:%M:%S")
            if quotes_updated_at_dtm is not None
            else None
        )


# TODO: Other models
class Quote(BaseSerializer):
    quote_number: str
    policy_number: Optional[str]
    quote_entry_date: datetime
    account_number: str
    product: str
    business_name: str
    phone_number: Optional[str]
    pol_jurisdiction_de: str
    last_contacted_advisor: Optional[str]
    create_contacted_advisor: Optional[str]
    transaction_status: str
    pol_effective_date: datetime
    last_entry_date: datetime
    quote_channel: str
    current_premium: float
    web_phone_in: int
    reject_reason: Optional[str]
    sqpm_quote_sale_reporting_in: int
    latest_scheduled_outbound_dt: Optional[datetime]
    expiry_dt: Optional[datetime]
    latest_result: Optional[str]


class QuoteHistory(BaseSerializer):
    quote_number: str
    policy_number: Optional[str]
    quote_entry_date: datetime
    account_number: str
    product: str
    business_name: str
    phone_number: Optional[str]
    pol_jurisdiction_de: str
    last_contacted_advisor: Optional[str]
    last_contacted_advisor_id: Optional[str]
    create_contacted_advisor: Optional[str]
    create_contacted_advisor_id: Optional[str]
    transaction_status: str
    pol_effective_date: datetime
    last_entry_date: datetime
    quote_channel: str
    current_premium: float
    web_phone_in: int
    reject_reason: Optional[str]
    sqpm_quote_sale_reporting_in: int


class Outbound(BaseSerializer):
    id: int
    quote_number: str
    user_id: str
    assigned_by: Optional[str]
    unassigned_by: Optional[str]
    result: Optional[str]
    is_inbound: Optional[bool]
    scheduled_outbound_dt: Optional[datetime]
    comment: Optional[str]
    assigned_at_dtm: Optional[datetime]
    started_at_dtm: Optional[datetime]
    completed_at_dtm: Optional[datetime]
    unassigned_at_dtm: Optional[datetime]
    created_at_dtm: datetime


class RepData(BaseSerializer):
    id: int
    date_type: str
    date_value: datetime
    product: str
    quote_channel: str
    quote_count: int
    sale_count: int
    sum_attempts: int
    new_leads_given: int
    new_leads_contacted: int
    leads_no_recontact_needed: int


class AttemptDetails(BaseSerializer):
    id: int
    date_type: str
    date_value: datetime
    product: str
    quote_channel: str
    series_name: str
    series_value: int


class MeltedAttemptData(BaseSerializer):
    date_value: datetime
    series_name: str
    series_value: int
