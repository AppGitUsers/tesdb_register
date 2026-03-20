from django.contrib import admin
from django import forms
from django.utils.translation import gettext_lazy as _
from .models import Staff, Course, Student, CourseTopic, StudentTopicProgress, Attendance , StudentAttendance ,Batch
from django.urls import path
from django.http import JsonResponse


# Customize admin site
admin.site.site_header = "TESDB ADMIN"   

# ----------------------------
# Course With Staff Filter
# ----------------------------
class CourseWithStaffFilter(admin.SimpleListFilter):
    title = _('course')
    parameter_name = 'course'

    def lookups(self, request, model_admin):
        qs = Course.objects.all().order_by('course_name')
        return [
            (c.pk, f"{c.course_name} ({', '.join([s.staff_name for s in c.staffs.all()])})")
            for c in qs
        ]

    def queryset(self, request, queryset):
        value = self.value()
        if value:
            return queryset.filter(course__pk=value)
        return queryset


# ----------------------------
# Student Form (show staff in course name)
# ----------------------------

class StudentAdminForm(forms.ModelForm):
    course = forms.ModelChoiceField(queryset=Course.objects.all(), required=True)
    staff = forms.ModelChoiceField(queryset=Staff.objects.none(), required=True)
    batch = forms.ModelChoiceField(queryset=Batch.objects.none(), required=False)

    class Meta:
        model = Student
        fields = ('student_name', 'join_date', 'end_date', 'course', 'staff', 
                  'student_email', 'student_contact', 'batch', 'mode')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        print(self.data.get('staff'))
        if 'course' in self.data:
            print("Course in data:", self.data.get('course'))
            try:
                course_id = int(self.data.get('course'))
                self.fields['staff'].queryset = Staff.objects.filter(courses__course_id=course_id)

            except (ValueError, TypeError):
                self.fields['staff'].queryset = Staff.objects.none()
        elif self.instance.pk and self.instance.course:
            self.fields['staff'].queryset = self.instance.course.staffs.all()
        
        if 'staff' in self.data:
            try:
                staff_id = int(self.data.get('staff'))
                self.fields['batch'].queryset = Batch.objects.filter(staff_id=staff_id)
            except (ValueError, TypeError):
                self.fields['batch'].queryset = Batch.objects.none()
        elif self.instance.pk and self.instance.staff:
            self.fields['batch'].queryset = Batch.objects.filter(staff=self.instance.staff)
        else:
            # Add this: no staff selected -> empty queryset
            self.fields['batch'].queryset = Batch.objects.none()

# ----------------------
# staff Course Filter
# ----------------------
class StaffCourseFilter(admin.SimpleListFilter):
    title = 'Course'
    parameter_name = 'course'

    def lookups(self, request, model_admin):
        courses = Course.objects.all()
        return [(c.pk, c.course_name) for c in courses]

    def queryset(self, request, queryset):
        value = self.value()
        if value:
            return queryset.filter(courses__pk=value)
        return queryset

class EmailDomainFilter(admin.SimpleListFilter):
    title = 'Email Domain'
    parameter_name = 'email_domain'

    def lookups(self, request, model_admin):
        return [
            ('gmail.com', 'Gmail'),
            ('outlook.com', 'Outlook'),
            ('yahoo.com', 'Yahoo'),
        ]

    def queryset(self, request, queryset):
        value = self.value()
        if value:
            return queryset.filter(staff_email__icontains=value)
        return queryset




# ----------------------------
# Staff Admin
# ----------------------------
@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ('staff_id', 'staff_name', 'contact', 'staff_email','get_courses')
    list_filter = (
        'staff_id',
        'staff_name',
        StaffCourseFilter,     # NEW FILTER 1
        EmailDomainFilter,     # NEW FILTER 2
        )

    def get_courses(self, obj):
        # Join all course names assigned to this staff
        return ", ".join([course.course_name for course in obj.courses.all()])
    get_courses.short_description = "Courses"


# ----------------------------
# Course Admin
# ----------------------------
@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('course_id', 'course_name', 'get_staff_names')
    list_filter = ('course_name',)
    def get_staff_names(self, obj):
        return ", ".join([s.staff_name for s in obj.staffs.all()])
    get_staff_names.short_description = "Staff"


# ----------------------------
# Staff by Course Filter
# ----------------------------
class StaffByCourseFilter(admin.SimpleListFilter):
    title = _('staff')
    parameter_name = 'staff'

    def lookups(self, request, model_admin):
        course_id = request.GET.get('course')
        if course_id:
            staffs = Staff.objects.filter(courses__course_id=course_id).distinct()
        else:
            staffs = Staff.objects.all().distinct()
        return [(staff.pk, staff.staff_name) for staff in staffs]

    def queryset(self, request, queryset):
        value = self.value()
        if value:
            return queryset.filter(staff_id=value)
        return queryset


# ----------------------------
# Student Admin
# ----------------------------
@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    form = StudentAdminForm
    list_display = ('student_id', 'student_name', 'join_date', 'course', 'staff','start_time','end_time')
    list_filter = (CourseWithStaffFilter,)
    search_fields = ('student_name',)

    @admin.display(description="Start Time")
    def start_time(self, obj):
        return obj.batch.start_time if obj.batch else "-"


    @admin.display(description="End Time")
    def end_time(self, obj):
        return obj.batch.end_time if obj.batch else "-"

    class Media:
        js = ("myapp/student_admin_v2.js",)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('getstaff/', self.admin_site.admin_view(self.get_staff), name='getstaff'),
            path('getbatches/', self.admin_site.admin_view(self.get_batches), name='getbatches'),
        ]
        return custom_urls + urls

    def get_staff(self, request):
        print(" get_staff called", request.GET)
        course_id = request.GET.get('course_id')
        staff_list = []
        if course_id:
            staffs = Staff.objects.filter(courses__course_id=course_id)
            staff_list = [{"id": s.staff_id, "name": s.staff_name} for s in staffs]
        return JsonResponse(staff_list, safe=False)
    
    def get_batches(self, request):
        """AJAX: return batches for a single staff (filtered)."""   
        staff_id = request.GET.get('staff_id')
        batch_list = []
        # debug log to server console
        print("DEBUG get_batches called, raw staff_id:", repr(staff_id))

        if staff_id:
            try:
                sid = int(staff_id)
            except (ValueError, TypeError):
                print("DEBUG get_batches: invalid staff_id, returning empty")
                return JsonResponse(batch_list, safe=False)

            # ensure we only filter by staff id
            batches = Batch.objects.filter(staff_id=sid).order_by('start_time')
            print("DEBUG get_batches: matched batches (ids):", list(batches.values_list('batch_id', flat=True)))

            batch_list = [{"id": b.batch_id, "name": str(b)} for b in batches]

        else:
            print("DEBUG get_batches: no staff_id provided in request")

        return JsonResponse(batch_list, safe=False)







# ----------------------------
# Course Topic Admin
# ----------------------------
@admin.register(CourseTopic)
class CourseTopicAdmin(admin.ModelAdmin):
    list_display = ('topic_id', 'course', 'module_name', 'topic_name')
    list_filter = ('course', 'module_name')


# ----------------------------
# Attendance Admin
# ----------------------------
@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("staff", "date", "time", "wifi_verified")
    list_filter = ("staff", "date", "wifi_verified")
    search_fields = ("staff__staff_name",)



@admin.register(StudentAttendance)
class StudentAttendanceAdmin(admin.ModelAdmin):
    list_display = ("student", "student_course", "student_staff", "date", "status")
    list_filter = ("status", "date", "student__course__course_name", "student__staff__staff_name")
    search_fields = ("student__student_name", "student__staff__staff_name", "student__course__course_name")

    def student_course(self, obj):
        return obj.student.course.course_name
    student_course.admin_order_field = "student__course__course_name"

    def student_staff(self, obj):
        return obj.student.staff.staff_name
    student_staff.admin_order_field = "student__staff__staff_name"


# --------------------------
# BATCH ADMIN
# --------------------------
@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display=("batch_id","staff","batch_name","start_time","end_time")
    list_filter=("staff","start_time","end_time",)
    search_fields=("staff","start_time",)

# ----------------------------
# Student Topic Progress Admin
# ----------------------------
from django.contrib import admin
from .models import StudentTopicProgress

@admin.register(StudentTopicProgress)
class StudentTopicProgressAdmin(admin.ModelAdmin):
    list_display = (
        'student_name', 
        'staff_name', 
        'course_name', 
        'module_name', 
        'topic_name', 
        'start_date', 
        'end_date', 
        'sign'
    )
    search_fields = ('student__student_name', 'topic__topic_name', 'sign')

    def student_name(self, obj):
        return obj.student.student_name

    def staff_name(self, obj):
        return obj.student.staff.staff_name if obj.student.staff else "Unassigned"

    def course_name(self, obj):
        return obj.topic.course.course_name

    def module_name(self, obj):
        return obj.topic.module_name

    def topic_name(self, obj):
        return obj.topic.topic_name
    
    list_filter = (
        'topic__course__course_name',
        'topic__module_name',
        'student__staff__staff_name',
        'student',
    )

    
