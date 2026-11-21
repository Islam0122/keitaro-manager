from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.offer import StreamOfferIn, validate_offer_shares

REDIRECT_ACTIONS = {
    "http", "meta", "double_meta", "js", "blank_referrer", "frame", "iframe", "curl", "remote", "formsubmit"
}
OTHER_ACTIONS = {"status404", "show_text", "show_html", "do_nothing"}


class StreamFilterIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    mode: Literal["accept", "reject"] = "accept"
    payload: Any = None

    @field_validator("payload")
    @classmethod
    def _payload(cls, value: Any) -> Any:
        if isinstance(value, list):
            return [v.strip() if isinstance(v, str) else v for v in value if v not in ("", None)]
        return value


class StreamIn(BaseModel):
    """Stream payload in Keitaro format (POST/PUT /admin_api/v1/streams)."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(min_length=1, max_length=255)
    type: Literal["regular", "forced", "default"] = "regular"
    position: int | None = Field(default=None, ge=0)
    weight: int | None = Field(default=None, ge=0, le=100)
    state: Literal["active", "disabled"] = "active"
    schema_: Literal["redirect", "landings", "action"] = Field(default="redirect", alias="schema")
    action_type: str = "http"
    action_payload: str | None = None
    filter_or: bool = False
    collect_clicks: bool = True
    comments: str | None = None
    filters: list[StreamFilterIn] = Field(default_factory=list)
    offers: list[StreamOfferIn] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check(self) -> "StreamIn":
        if self.type == "default" and self.filters:
            raise ValueError("Поток типа default не может иметь фильтров")
        for flt in self.filters:
            if flt.name == "country":
                codes = flt.payload if isinstance(flt.payload, list) else []
                if not codes or any(not (isinstance(c, str) and len(c) == 2 and c.isalpha()) for c in codes):
                    raise ValueError("GEO-фильтр должен содержать ISO-коды стран из двух букв")
                flt.payload = [c.upper() for c in codes]
        if self.schema_ == "redirect":
            if self.action_type not in REDIRECT_ACTIONS:
                raise ValueError("Недопустимый тип редиректа")
            url = (self.action_payload or "").strip()
            if not url.startswith(("http://", "https://")):
                raise ValueError("Для редиректа укажите целевой URL, начинающийся с http:// или https://")
            self.action_payload = url
            self.offers = []
        elif self.schema_ == "landings":
            if not self.offers:
                raise ValueError("Добавьте в поток хотя бы один оффер")
            validate_offer_shares(self.offers)
            self.action_type = self.action_type if self.action_type in REDIRECT_ACTIONS else "http"
        else:
            if self.action_type not in OTHER_ACTIONS:
                raise ValueError("Недопустимое действие потока")
            self.offers = []
        return self

    def to_keitaro(self, campaign_id: int) -> dict[str, Any]:
        payload = self.model_dump(by_alias=True, exclude_none=True)
        payload["campaign_id"] = campaign_id
        return payload
