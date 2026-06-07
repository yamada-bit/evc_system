from django.contrib import admin

# Register your models here.
from Kms_Attendance.models import (
    M_emp,
    M_holiday,
    M_kbn,
    M_ltd,
    M_nendo,
    M_tdfuken,
    M_work_pat,
    M_yukyu,
)

admin.site.register(M_emp)
admin.site.register(M_ltd)
admin.site.register(M_holiday)
admin.site.register(M_tdfuken)
admin.site.register(M_work_pat)
admin.site.register(M_nendo)
admin.site.register(M_kbn)
admin.site.register(M_yukyu)
