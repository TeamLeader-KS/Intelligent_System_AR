from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Literal
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator
from .schemas import EquipmentOut, InspectionOut


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class ModelLabel(StrictBody):
    class_id: int = Field(ge=0, le=255, strict=True)
    name: str = Field(min_length=1, max_length=160, pattern=r"\S")
    kind: Literal["DEFECT", "NORMAL", "UNKNOWN"]
    defect_type_id: int | None = Field(default=None, gt=0, strict=True)

    @model_validator(mode="after")
    def defect_mapping(self):
        if self.kind != "DEFECT" and self.defect_type_id is not None:
            raise ValueError("Только дефект связывается с каталогом неисправностей")
        return self


class NewMobileModel(StrictBody):
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    version: str = Field(min_length=1, max_length=160, pattern=r"\S")
    threshold: float = Field(default=0.4, ge=0, lt=1)
    labels: list[ModelLabel] = Field(min_length=1, max_length=256)

    @model_validator(mode="after")
    def label_order(self):
        if [label.class_id for label in self.labels] != list(range(len(self.labels))):
            raise ValueError("Нужен полный подтверждённый список классов по порядку, начиная с 0")
        return self


class FrameSize(StrictBody):
    width: int = Field(gt=0, le=20000, strict=True)
    height: int = Field(gt=0, le=20000, strict=True)

    @model_validator(mode="after")
    def pixels(self):
        if self.width * self.height > 20_000_000:
            raise ValueError("Превышен размер кадра")
        return self


Coordinate = Annotated[float, Field(ge=0, le=1)]


class DeviceFinding(StrictBody):
    class_id: int = Field(ge=0, le=255, strict=True)
    confidence: float = Field(ge=0, le=1)
    # Already mapped by Android to the upright source frame, not the 640x640 letterbox.
    box: tuple[Coordinate, Coordinate, Coordinate, Coordinate] | None = None

    @field_validator("box")
    @classmethod
    def ordered_box(cls, value):
        if value is not None and (value[0] >= value[2] or value[1] >= value[3]):
            raise ValueError("Ожидается нормализованная рамка [x_min,y_min,x_max,y_max]")
        return value


class SensorReading(StrictBody):
    name: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_.-]+$")
    value: float
    unit: str = Field(min_length=1, max_length=40, pattern=r"\S")
    measured_at: AwareDatetime
    source: Literal["SENSOR", "MANUAL", "DEMO"]


class VisualCheck(StrictBody):
    code: Literal["SEAL_LEAK", "FRAME_CORROSION", "LOOSE_ANCHOR", "OIL_DARK", "OIL_LOW", "TERMINAL_OXIDATION", "COUPLING_GUARD_MISSING"]
    observed: bool
    source: Literal["MANUAL"] = "MANUAL"


class NewDiagnosticPreview(StrictBody):
    component_id: int = Field(gt=0, strict=True)
    captured_at: AwareDatetime
    telemetry: list[SensorReading] = Field(default_factory=list, max_length=50)
    visual_checks: list[VisualCheck] = Field(default_factory=list, max_length=7)

    @field_validator("captured_at")
    @classmethod
    def capture_time(cls, value):
        if value > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("Время в будущем")
        return value.astimezone(timezone.utc)


class NewDeviceInspection(StrictBody):
    equipment_id: int = Field(gt=0, strict=True)
    component_id: int | None = Field(default=None, gt=0, strict=True)
    source: Literal["CAMERA", "GALLERY"] = "CAMERA"
    captured_at: AwareDatetime
    model_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    image: FrameSize
    defects: list[DeviceFinding] = Field(max_length=100)
    telemetry: list[SensorReading] = Field(default_factory=list, max_length=50)
    visual_checks: list[VisualCheck] = Field(default_factory=list, max_length=7)
    comment: str = Field(default="", max_length=2000)

    @field_validator("captured_at")
    @classmethod
    def capture_time(cls, value):
        value = value.astimezone(timezone.utc)
        if value > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("Время съёмки в будущем")
        return value


class Specification(StrictBody):
    name: str = Field(min_length=1, max_length=80, pattern=r"\S")
    value: float
    unit: str = Field(min_length=1, max_length=40, pattern=r"\S")
    minimum: float | None = None
    maximum: float | None = None

    @model_validator(mode="after")
    def bounds(self):
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("Неверный диапазон нормы")
        return self


class NewComponent(StrictBody):
    name: str = Field(min_length=1, max_length=160, pattern=r"\S")
    model: str = Field(default="", max_length=160)
    specifications: list[Specification] = Field(default_factory=list, max_length=50)
    installed_on: date | None = None
    lifetime_days: int | None = Field(default=None, gt=0, le=100000)
    lifetime_hours: float | None = Field(default=None, gt=0, le=1e9)
    lifetime_cycles: int | None = Field(default=None, gt=0, le=2_000_000_000)
    operating_hours: float | None = Field(default=None, ge=0, le=1e9)
    operating_cycles: int | None = Field(default=None, ge=0, le=2_000_000_000)
    service_interval_hours: float | None = Field(default=None, gt=0, le=1e9)
    last_service_hours: float | None = Field(default=None, ge=0, le=1e9)

    @model_validator(mode="after")
    def dates_and_usage(self):
        if self.installed_on and self.installed_on > datetime.now(timezone.utc).date():
            raise ValueError("Дата установки в будущем")
        if self.last_service_hours is not None and (self.operating_hours is None or self.last_service_hours > self.operating_hours):
            raise ValueError("Наработка последнего обслуживания превышает текущую")
        return self


class NewComponentWork(StrictBody):
    action: Literal["INSPECTED", "SERVICED", "REPLACED", "READINGS", "STARTED", "STOPPED"]
    occurred_at: AwareDatetime
    expected_revision: int = Field(ge=0, strict=True)
    comment: str = Field(min_length=1, max_length=2000, pattern=r"\S")
    operating_hours: float | None = Field(default=None, ge=0, le=1e9)
    operating_cycles: int | None = Field(default=None, ge=0, le=2_000_000_000)

    @model_validator(mode="after")
    def event_time(self):
        self.occurred_at = self.occurred_at.astimezone(timezone.utc)
        if self.occurred_at > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("Работы не могут быть выполнены в будущем")
        if self.action == "REPLACED" and (self.operating_hours not in (None, 0) or self.operating_cycles not in (None, 0)):
            raise ValueError("После замены наработка нового компонента начинается с нуля")
        return self


class ResourceMeasure(BaseModel):
    norm: float | None
    used: float | None
    remaining: float | None


class ComponentResource(BaseModel):
    basis: Literal["NORMATIVE"]
    estimates: dict[str, ResourceMeasure]
    status: Literal["DUE", "APPROACHING", "WITHIN_NORM", "INSUFFICIENT_DATA"]
    service_remaining_hours: float | None
    service_due: bool | None
    limitations: str


class ComponentOut(NewComponent):
    id: int
    equipment_id: int
    revision: int
    last_serviced_at: AwareDatetime | None
    last_event_at: AwareDatetime | None
    runtime_state: Literal["RUNNING", "STOPPED"] = "STOPPED"
    run_started_at: AwareDatetime | None = None


class ComponentCard(ComponentOut):
    resource: ComponentResource


class EquipmentDigitalCard(EquipmentOut):
    qr_code: str
    components: list[ComponentCard]


class ComponentWorkOut(NewComponentWork):
    work_id: int
    component_id: int
    equipment_id: int
    author_id: int
    recorded_at: AwareDatetime
    before: ComponentOut
    after: ComponentOut
    resource: ComponentResource


class WorkHistoryOut(BaseModel):
    items: list[ComponentWorkOut]
    total: int
    limit: int
    offset: int


class DiagnosticPreviewOut(BaseModel):
    diagnostics: list[dict]
    ignored_readings: list[str]
    limitations: str
    component_resource: ComponentResource
    component_id: int
    saved: Literal[False] = False


class PhotoAttachedOut(BaseModel):
    photo_id: int


class SavedFinding(DeviceFinding):
    class_name: str
    kind: Literal["DEFECT", "NORMAL", "UNKNOWN"]
    defect_id: int | None
    accepted: bool


class DeviceInspectionOut(InspectionOut):
    analysis_location: Literal["ANDROID"]
    model_sha256: str
    captured_at: AwareDatetime
    component_id: int | None
    threshold: float
    detections: list[SavedFinding]
    telemetry: list[SensorReading]
    telemetry_source: Literal["CLIENT_REPORTED"]
    visual_checks: list[VisualCheck] = Field(default_factory=list)
    comment: str = ""
    diagnostics: list[dict] = Field(default_factory=list)
    component_resource: dict | None = None
    diagnostic_limitations: str = ""
    ignored_readings: list[str] = Field(default_factory=list)
