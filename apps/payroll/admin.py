from django.contrib import admin

from .models import SalaryRecord, WorkerProfile


@admin.register(WorkerProfile)
class WorkerProfileAdmin(admin.ModelAdmin):
    list_display = ("employee_code", "user", "hub", "job_title", "monthly_salary", "is_active")
    list_filter = ("is_active", "hub")
    search_fields = ("employee_code", "user__username", "user__first_name", "user__last_name")
    autocomplete_fields = ("user", "hub")


@admin.register(SalaryRecord)
class SalaryRecordAdmin(admin.ModelAdmin):
    list_display = ("worker", "period_start", "gross_amount", "net_amount", "status", "paid_at")
    list_filter = ("status", "period_start")
    search_fields = ("worker__employee_code", "worker__user__username")
    readonly_fields = tuple(field.name for field in SalaryRecord._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False