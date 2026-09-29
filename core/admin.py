from django.contrib import admin

from .models import AIConfig, ApiCallLog, Summary


@admin.register(Summary)
class SummaryAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "user", "kind", "language", "input_words", "summary_words", "latency_ms",
                    "is_favorite", "created_at")
    list_filter = ("language", "kind", "is_favorite", "created_at")
    search_fields = ("title", "input_text", "summary", "user__username")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"


@admin.register(ApiCallLog)
class ApiCallLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "method", "endpoint", "status_code", "ok", "latency_ms", "user")
    list_filter = ("ok", "endpoint", "method")
    search_fields = ("endpoint", "error")
    date_hierarchy = "created_at"


@admin.register(AIConfig)
class AIConfigAdmin(admin.ModelAdmin):
    list_display = ("effective_url", "timeout", "updated_at")

    def has_add_permission(self, request):
        return not AIConfig.objects.exists()
