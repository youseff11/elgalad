import uuid

from django.conf import settings
from django.db import models


class AIConfig(models.Model):
    """Singleton row holding the AI model connection + default generation params.

    Editable by staff from the dashboard (Settings → AI Model) so a new
    Cloudflare tunnel URL can be plugged in without touching code.
    """

    base_url = models.URLField(max_length=500, blank=True, help_text="Leave empty to use AI_API_BASE_URL from .env")
    timeout = models.PositiveIntegerField(default=120)
    default_max_length = models.PositiveIntegerField(default=128)
    default_min_length = models.PositiveIntegerField(default=20)
    default_num_beams = models.PositiveIntegerField(default=4)
    default_length_penalty = models.FloatField(default=1.0)
    default_repetition_penalty = models.FloatField(default=1.2)
    default_no_repeat_ngram_size = models.PositiveIntegerField(default=3)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "AI model configuration"
        verbose_name_plural = "AI model configuration"

    def __str__(self):
        return self.effective_url

    @property
    def effective_url(self) -> str:
        return (self.base_url or settings.AI_API_BASE_URL).rstrip("/")

    @classmethod
    def get(cls) -> "AIConfig":
        obj, _ = cls.objects.get_or_create(pk=1, defaults={"timeout": settings.AI_API_TIMEOUT})
        return obj

    def default_params(self) -> dict:
        return {
            "max_length": self.default_max_length,
            "min_length": self.default_min_length,
            "num_beams": self.default_num_beams,
            "length_penalty": self.default_length_penalty,
            "repetition_penalty": self.default_repetition_penalty,
            "no_repeat_ngram_size": self.default_no_repeat_ngram_size,
        }


class Summary(models.Model):
    KIND_SINGLE = "single"
    KIND_BATCH = "batch"
    KIND_CHOICES = [(KIND_SINGLE, "Single"), (KIND_BATCH, "Batch")]

    SOURCE_TEXT = "text"
    SOURCE_FILE = "file"
    SOURCE_CHOICES = [(SOURCE_TEXT, "Text"), (SOURCE_FILE, "File")]

    LANG_CHOICES = [("ar", "Arabic"), ("en", "English"), ("mixed", "Mixed"), ("unknown", "Unknown")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="summaries")
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default=KIND_SINGLE)
    batch_id = models.UUIDField(null=True, blank=True, db_index=True)
    source_type = models.CharField(max_length=10, choices=SOURCE_CHOICES, default=SOURCE_TEXT)
    file_name = models.CharField(max_length=255, blank=True)

    title = models.CharField(max_length=200, blank=True)
    input_text = models.TextField()
    cleaned_text = models.TextField(blank=True)
    summary = models.TextField(blank=True)

    language = models.CharField(max_length=10, choices=LANG_CHOICES, default="unknown", db_index=True)
    confidence = models.FloatField(null=True, blank=True)
    input_words = models.PositiveIntegerField(default=0)
    summary_words = models.PositiveIntegerField(default=0)
    latency_ms = models.FloatField(null=True, blank=True)
    params = models.JSONField(default=dict, blank=True)
    token_stats = models.JSONField(default=dict, blank=True)

    is_favorite = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Summaries"

    def __str__(self):
        return self.title or f"Summary #{self.pk}"

    @property
    def compression(self) -> float:
        """Percentage of text removed (0–100)."""
        if not self.input_words:
            return 0.0
        return max(0.0, round((1 - self.summary_words / self.input_words) * 100, 1))

    @property
    def latency_s(self):
        return round(self.latency_ms / 1000, 2) if self.latency_ms else None

    @property
    def is_rtl(self) -> bool:
        return self.language in ("ar", "mixed")


class ApiCallLog(models.Model):
    """Every call Django makes to the AI model — powers the monitoring page."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    endpoint = models.CharField(max_length=100, db_index=True)
    method = models.CharField(max_length=8, default="POST")
    status_code = models.PositiveIntegerField(null=True, blank=True)
    ok = models.BooleanField(default=False, db_index=True)
    latency_ms = models.FloatField(null=True, blank=True)
    error = models.TextField(blank=True)
    request_id = models.UUIDField(default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.method} {self.endpoint} → {self.status_code}"
