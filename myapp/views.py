from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.http import FileResponse
from .models import (
    Student, StudentTopicProgress, Staff, CourseTopic,
    Attendance, StudentAttendance, Batch, Course,
    StaffCourseProgress, StaffLeave, StaffLeaveUsage,CompanyInterview,StudentProgressDashboard,JobApplication
)
from django.contrib import messages
from django.forms import modelformset_factory
from django import forms
from django.utils.timezone import now, localdate
from django.utils import timezone
from django.urls import reverse
from datetime import date, datetime
import logging
import json
import calendar
import os
import uuid
from dateutil.relativedelta import relativedelta
from django.views.decorators.http import require_POST
#bio
import urllib.parse
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
logger = logging.getLogger(__name__)


def home(request):
    return render(request, 'home.html')


def register_staff(request):
    if request.method == "POST":
        username         = request.POST.get('username')
        password         = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists!!')
            return render(request, 'register_staff.html')
        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'register_staff.html')
        if len(password) <= 8:
            messages.error(request, 'Password must be at least 8 characters long.')
            return render(request, 'register_staff.html')

        User.objects.create_user(username=username, password=password).save()
        messages.success(request, 'Registered successfully!!')
        return redirect('staff_login')

    return render(request, 'register_staff.html')


def staff_login(request):
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            if hasattr(user, 'staff'):
                staff=user.staff

                if staff.courses.filter(course_name__iexact="placement").exists():
                    return redirect('placement_dashboard')
                return redirect('get_batches')
            return redirect('home')
        else:
            messages.error(request, "Invalid username or password.")
    return render(request, 'staff_login.html')


def staff_logout(request):
    logout(request)
    return redirect('staff_login')


@login_required
def getBatches(request):
    staff   = get_object_or_404(Staff, user=request.user)
    batches = Batch.objects.filter(staff=staff).order_by('start_time')
    staff_courses = staff.courses.all()

    courses_with_progress = []
    for c in Course.objects.prefetch_related('topics').all():
        done = StaffCourseProgress.objects.filter(staff=staff, topic__course=c, completed=True).count()
        c.completed_count = done
        courses_with_progress.append(c)

    return render(request, 'batch.html', {
        'batches':                  batches,
        'staff':                    staff,
        'staff_courses':            staff_courses,
        'all_courses_for_learning': courses_with_progress,
        'today':                    str(localdate()),
    })


@login_required
def add_batch(request):
    staff = get_object_or_404(Staff, user=request.user)
    if request.method == "POST":
        batch_name = request.POST["batch_name"]
        start_time = request.POST["start_time"]
        end_time   = request.POST["end_time"]
        if start_time >= end_time:
            messages.error(request, "Start time must be less than End time.")
            return redirect("add_batch")
        Batch.objects.create(staff=staff, batch_name=batch_name, start_time=start_time, end_time=end_time)
        messages.success(request, "New batch added successfully!")
        return redirect("get_batches")
    return render(request, "add_batch.html")


@login_required
def edit_batch(request, batch_id):
    staff = get_object_or_404(Staff, user=request.user)
    batch = get_object_or_404(Batch, pk=batch_id, staff=staff)
    if request.method == "POST":
        batch_name = request.POST["batch_name"]
        start_time = request.POST["start_time"]
        end_time   = request.POST["end_time"]
        if not batch_name or not start_time or not end_time:
            messages.error(request, "All fields are required.")
            return redirect("edit_batch", batch_id=batch_id)
        if start_time >= end_time:
            messages.error(request, "Start time must be less than End time.")
            return redirect("edit_batch", batch_id=batch_id)
        batch.batch_name = batch_name
        batch.start_time = start_time
        batch.end_time   = end_time
        batch.save()
        messages.success(request, "Batch updated successfully!")
        return redirect('get_batches')
    return render(request, "add_batch.html", {"batch": batch})


@login_required
def delete_batch(request, batch_id):
    staff = get_object_or_404(Staff, user=request.user)
    batch = get_object_or_404(Batch, pk=batch_id, staff=staff)
    if request.method == "POST":
        if Student.objects.filter(batch=batch).count() > 0:
            messages.error(request, "Cannot delete batch with assigned students.")
            return redirect('get_batches')
        batch.delete()
        messages.success(request, "Batch deleted successfully.")
        return redirect('get_batches')
    return redirect('get_batches')


@login_required
def student_list(request, batch_id):
    staff    = get_object_or_404(Staff, user=request.user)
    batch    = get_object_or_404(Batch, pk=batch_id, staff=staff)
    students = Student.objects.filter(staff=staff, batch=batch)
    batches  = Batch.objects.filter(staff=staff)
    today    = localdate()
    attendance = Attendance.objects.filter(staff=staff, date=today).last()

    if request.method == "POST":
        student_id   = request.POST.get('student_id')
        new_batch_id = request.POST.get('batch')
        student      = get_object_or_404(Student, pk=student_id, staff=staff)
        if new_batch_id:
            student.batch = get_object_or_404(Batch, pk=new_batch_id, staff=staff)
        mode = request.POST.get('mode')
        if mode in ['True', 'False']:
            student.mode = mode == 'True'
        student.save()
        return redirect('student_list', batch_id=batch_id)

    return render(request, 'student_list.html', {
        'students':    students,
        'attendance':  attendance,
        'batch':       batch,
        'all_batches': batches,
        'batches':     batches,
    })


@login_required
def student_detail(request, student_id, batch_id):
    student = get_object_or_404(Student, pk=student_id)
    if hasattr(request.user, 'staff'):
        if student.staff != request.user.staff:
            return redirect('home')

    topics = CourseTopic.objects.filter(course=student.course).order_by('topic_id')
    progress_dict = {p.topic_id: p for p in StudentTopicProgress.objects.filter(student=student)}
    topic_progress_list = [{"topic": t, "progress": progress_dict.get(t.pk)} for t in topics]

    return render(request, 'student_detail.html', {
        'student':             student,
        'topic_progress_list': topic_progress_list,
        'batch_id':            batch_id,
    })


@login_required
def add_progress(request, student_id, batch_id):
    staff   = get_object_or_404(Staff, user=request.user)
    student = get_object_or_404(Student, pk=student_id, staff=staff)
    batch   = get_object_or_404(Batch, pk=batch_id)

    topics = CourseTopic.objects.filter(course=student.course).order_by('topic_id')
    for topic in topics:
        StudentTopicProgress.objects.get_or_create(student=student, topic=topic)

    class ProgressForm(forms.ModelForm):
        class Meta:
            model   = StudentTopicProgress
            fields  = ('start_date', 'end_date', 'marks')
            widgets = {
                'start_date': forms.DateInput(attrs={'type': 'date'}),
                'end_date':   forms.DateInput(attrs={'type': 'date'}),
            }

    ProgressFormSet = modelformset_factory(StudentTopicProgress, form=ProgressForm, extra=0)
    queryset = StudentTopicProgress.objects.filter(student=student).order_by('topic__topic_id')

    if request.method == "POST":
        formset = ProgressFormSet(request.POST, queryset=queryset)
        if formset.is_valid():
            for form in formset.forms:
                progress = form.save(commit=False)
                if form.has_changed():
                    progress.sign = staff.staff_name
                progress.save()
                form.save_m2m()
            update_single_student_progress(student)
            return redirect('student_detail', student_id=student.pk, batch_id=batch.pk)
    else:
        formset = ProgressFormSet(queryset=queryset)

    return render(request, 'add_progress.html', {
        'student':          student,
        'formset':          formset,
        'topic_form_pairs': list(zip(formset.forms, topics)),
        'batch_id':         batch.pk,
    })


@login_required
def mark_student_attendance(request, batch_id):
    staff    = get_object_or_404(Staff, user=request.user)
    batch    = get_object_or_404(Batch, pk=batch_id, staff=staff)
    students = Student.objects.filter(staff=staff, batch=batch)
    today    = timezone.now().date()

    date_str = request.POST.get("date") or request.GET.get("date")
    try:
        selected_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else today
    except ValueError:
        selected_date = today
    if selected_date > today:
        selected_date = today

    if request.method == "POST":
        for student in students:
            status = request.POST.get(f"status_{student.student_id}")
            if status is not None:
                status_bool = status == "present"
                att, created = StudentAttendance.objects.get_or_create(
                    student=student, date=selected_date, defaults={"status": status_bool}
                )
                if not created:
                    att.status = status_bool
                    att.save()
        return redirect(
            f"{reverse('student_attendance', args=[batch.batch_id])}"
            f"?date={selected_date.strftime('%Y-%m-%d')}"
        )

    attendance_records = {
        att.student_id: att
        for att in StudentAttendance.objects.filter(date=selected_date, student__in=students)
    }
    return render(request, "student_attendance.html", {
        "students":           students,
        "attendance_records": attendance_records,
        "today":              today.strftime("%Y-%m-%d"),
        "selected_date":      selected_date.strftime("%Y-%m-%d"),
        "batch":              batch,
    })


@login_required
def staff_add_student(request):
    if request.method == 'POST':
        try:
            staff           = get_object_or_404(Staff, user=request.user)
            student_name    = request.POST['student_name'].strip()
            student_email   = request.POST['student_email'].strip()
            student_contact = request.POST.get('student_contact', '').strip()
            join_date       = request.POST['join_date']
            course_id       = request.POST['course']
            batch_id        = request.POST.get('batch') or None
            mode            = request.POST.get('mode', 'True') == 'True'
            course = get_object_or_404(Course, pk=course_id)
            if not staff.courses.filter(pk=course_id).exists():
                messages.error(request, 'You are not assigned to that course.')
                return redirect('get_batches')
            batch = get_object_or_404(Batch, pk=batch_id, staff=staff) if batch_id else None
            student = Student.objects.create(
                student_name=student_name,
                student_email=student_email,
                student_contact=student_contact,
                join_date=join_date,
                course=course,
                staff=staff,
                batch=batch,
                mode=mode,
            )
            update_single_student_progress(student)
            messages.success(request, f'Student "{student_name}" added successfully!')

            # # ✅ Progress creation
            # topics_count = course.topics.count()

            # StudentProgressDashboard.objects.update_or_create(
            #     student=student,
            #     defaults={
            #         "total_topics": topics_count,
            #         "finished_topics": 0
            #     }
            # )
        except Exception as e:
            messages.error(request, f'Error adding student: {e}')
    return redirect('get_batches')


@login_required
def staff_course_topics(request, course_id):
    staff  = get_object_or_404(Staff, user=request.user)
    course = get_object_or_404(Course, pk=course_id)
    topics = CourseTopic.objects.filter(course=course).order_by('topic_id')
    progress_map = {}
    for t in topics:
        prog, _ = StaffCourseProgress.objects.get_or_create(staff=staff, topic=t)
        progress_map[t.topic_id] = prog.completed
    return JsonResponse({
        'course_id': course_id, 'course_name': course.course_name,
        'topics': [{'topic_id': t.topic_id, 'module_name': t.module_name,
                    'topic_name': t.topic_name, 'completed': progress_map.get(t.topic_id, False)}
                   for t in topics],
    })


@login_required
def staff_toggle_topic(request, topic_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    staff = get_object_or_404(Staff, user=request.user)
    topic = get_object_or_404(CourseTopic, pk=topic_id)
    body      = json.loads(request.body or '{}')
    completed = body.get('completed', False)
    prog, _           = StaffCourseProgress.objects.get_or_create(staff=staff, topic=topic)
    prog.completed    = completed
    prog.completed_at = now() if completed else None
    prog.save()
    all_topics = CourseTopic.objects.filter(course=topic.course).count()
    done_count = StaffCourseProgress.objects.filter(staff=staff, topic__course=topic.course, completed=True).count()
    return JsonResponse({'ok': True, 'done_count': done_count, 'total': all_topics})


# ── ADMIN DASHBOARD ───────────────────────────
@staff_member_required
def admin_dashboard(request):
    from django.db.models import Count
    today = localdate()

    courses_qs = Course.objects.annotate(student_count=Count('students'))
    max_count  = max((c.student_count for c in courses_qs), default=1) or 1

    stats = {
        'total_students':    Student.objects.count(),
        'total_staff':       Staff.objects.count(),
        'total_courses':     Course.objects.count(),
        'total_topics':      CourseTopic.objects.count(),
        'total_batches':     Batch.objects.count(),
        'online_students':   Student.objects.filter(mode=False).count(),
        'present_today':     StudentAttendance.objects.filter(date=today, status=True).count(),
        'absent_today':      StudentAttendance.objects.filter(date=today, status=False).count(),
        'today_attendance':  StudentAttendance.objects.filter(date=today, status=True).count(),
        'course_enrollment': [{'name': c.course_name, 'count': c.student_count,
                                'pct': round(c.student_count / max_count * 100)} for c in courses_qs],
        'recent_students':   Student.objects.select_related('course', 'staff').order_by('-join_date')[:8],
        'staff_overview':    [{'staff_name': s.staff_name, 'course_count': s.courses.count(),
                                'student_count': s.students.count(), 'batch_count': s.batches.count()}
                              for s in Staff.objects.all()],
    }

    raw_att = Attendance.objects.select_related('staff').filter(date=today).order_by('staff__staff_name', 'time')
    staff_att_map = {}
    for a in raw_att:
        sid = a.staff_id
        if sid not in staff_att_map:
            staff_att_map[sid] = {'staff': a.staff, 'date': a.date, 'login': None, 'logout': None}
        if a.verify_code not in ('1', '5') and staff_att_map[sid]['login'] is None:
            staff_att_map[sid]['login'] = a.time
        if a.verify_code in ('1', '5'):
            staff_att_map[sid]['logout'] = a.time
    all_staff_attendance = list(staff_att_map.values())
    
    dashboards = StudentProgressDashboard.objects.select_related(
    "student", "student__course"
    ).all()

    return render(request, 'admin_dashboard.html', {
        'staffs': Staff.objects.all(),
        'courses': Course.objects.all(),
        'stats':                  stats,
        'dashboards' :            dashboards,
        'all_students':           Student.objects.select_related('course', 'staff', 'batch').all(),
        'all_staff':              Staff.objects.prefetch_related('courses').all(),
        'all_courses':            Course.objects.prefetch_related('staffs').all(),
        'all_topics':             CourseTopic.objects.select_related('course').all(),
        'all_progress':           StudentTopicProgress.objects.select_related('student', 'topic', 'topic__course').all()[:200],
        'all_batches':            Batch.objects.select_related('staff').all(),
        'all_student_attendance': StudentAttendance.objects.select_related('student', 'student__course', 'student__staff').filter(date=today).order_by('-date')[:100],
        'all_staff_attendance':   all_staff_attendance,
        'today':                  str(today),
    })


@staff_member_required
def admin_get_staff(request):
    course_id = request.GET.get('course_id')
    data = [{'id': s.staff_id, 'name': s.staff_name}
            for s in Staff.objects.filter(courses__course_id=course_id)] if course_id else []
    return JsonResponse(data, safe=False)


@staff_member_required
def admin_get_batches(request):
    staff_id = request.GET.get('staff_id')
    data = []
    if staff_id:
        try:
            data = [{'id': b.batch_id, 'name': str(b)}
                    for b in Batch.objects.filter(staff_id=int(staff_id)).order_by('start_time')]
        except (ValueError, TypeError):
            pass
    return JsonResponse(data, safe=False)


@staff_member_required
def admin_add_student(request):
    if request.method == 'POST':
        try:
            course = get_object_or_404(Course, pk=request.POST['course'])
            staff_id = request.POST.get('staff') or None
            batch_id = request.POST.get('batch') or None
            student = Student.objects.create(
                student_name=request.POST['student_name'].strip(),
                student_email=request.POST['student_email'].strip(),
                student_contact=request.POST.get('student_contact', '').strip(),
                join_date=request.POST['join_date'],
                course=course,
                staff=get_object_or_404(Staff, pk=staff_id) if staff_id else None,
                batch=get_object_or_404(Batch, pk=batch_id) if batch_id else None,
                mode=request.POST.get('mode', 'True') == 'True',
            )
            update_single_student_progress(student)
            messages.success(request, f'Student added successfully!')
        except Exception as e:
            messages.error(request, f'Error: {e}')
    return redirect('admin_dashboard')


@staff_member_required
def admin_add_course(request):
    if request.method == 'POST':
        name = request.POST.get('course_name', '').strip()
        if name:
            obj, created = Course.objects.get_or_create(course_name=name.capitalize())
            messages.success(request, f'Course "{obj.course_name}" created!') if created else messages.error(request, 'Course already exists.')
        else:
            messages.error(request, 'Course name cannot be empty.')
    return redirect('admin_dashboard')


@staff_member_required
def admin_add_topic(request):
    if request.method == 'POST':
        try:
            course = get_object_or_404(Course, pk=request.POST['course'])
            obj, created = CourseTopic.objects.get_or_create(
                course=course,
                module_name=request.POST['module_name'].strip().capitalize(),
                topic_name=request.POST['topic_name'].strip().capitalize(),
            )
            messages.success(request, f'Topic added!') if created else messages.error(request, 'Topic already exists.')
        except Exception as e:
            messages.error(request, f'Error: {e}')
    return redirect('admin_dashboard')


@staff_member_required
def admin_add_staff(request):
    if request.method == 'POST':
        try:
            username = request.POST['username'].strip()
            if User.objects.filter(username=username).exists():
                messages.error(request, 'Username already exists.')
                return redirect('admin_dashboard')
            user  = User.objects.create_user(username=username, password=request.POST['password'])
            staff = Staff.objects.create(
                user=user,
                staff_name=request.POST['staff_name'].strip(),
                staff_email=request.POST['staff_email'].strip(),
                contact=request.POST.get('contact', '').strip(),
            )
            course_ids = request.POST.getlist('courses')
            if course_ids:
                staff.courses.set(Course.objects.filter(pk__in=course_ids))
            messages.success(request, f'Staff created!')
        except Exception as e:
            messages.error(request, f'Error: {e}')
    return redirect('admin_dashboard')


@staff_member_required
def admin_enroll_staff(request):
    if request.method == 'POST':
        mode = request.POST.get('mode')
        try:
            if mode == 'existing':
                user = get_object_or_404(User, pk=request.POST['user_id'])
                if Staff.objects.filter(user=user).exists():
                    messages.error(request, 'That user already has a Staff profile.')
                    return redirect('admin_dashboard')
                staff = Staff.objects.create(
                    user=user,
                    staff_name=request.POST['staff_name'].strip(),
                    staff_email=request.POST['staff_email'].strip(),
                    contact=request.POST.get('contact', '').strip(),
                )
            else:
                username = request.POST['username'].strip()
                if User.objects.filter(username=username).exists():
                    messages.error(request, 'Username already exists.')
                    return redirect('admin_dashboard')
                user  = User.objects.create_user(username=username, password=request.POST['password'])
                staff = Staff.objects.create(
                    user=user,
                    staff_name=request.POST['staff_name'].strip(),
                    staff_email=request.POST['staff_email'].strip(),
                    contact=request.POST.get('contact', '').strip(),
                )
            course_ids = request.POST.getlist('courses')
            if course_ids:
                staff.courses.set(Course.objects.filter(pk__in=course_ids))
            messages.success(request, f'Staff "{staff.staff_name}" enrolled!')
        except Exception as e:
            messages.error(request, f'Error: {e}')
    return redirect('admin_dashboard')


# ── LEAVE HELPER ──────────────────────────────
def _credit_monthly_leave(leave_obj, today=None):
    if today is None:
        today = date.today()
    unlock_date = leave_obj.join_date + relativedelta(months=3)
    if today < unlock_date:
        return
    credit_from         = leave_obj.last_credited or unlock_date
    current_month_start = today.replace(day=1)
    months_due          = 0
    cursor              = credit_from.replace(day=1)
    while cursor < current_month_start:
        cursor += relativedelta(months=1)
        months_due += 1
    if months_due > 0:
        leave_obj.leave_balance += months_due
        leave_obj.last_credited  = current_month_start - relativedelta(months=1)
        leave_obj.save()


# ── STAFF CALENDAR HELPER ─────────────────────
def _build_staff_calendar(staff, year, month):
    today = date.today()

    from collections import defaultdict
    daily_punches = defaultdict(lambda: {'in': None, 'out': None})

    for a in Attendance.objects.filter(
        staff=staff, date__year=year, date__month=month
    ).order_by('time'):
        pt = 'out' if a.verify_code in ('1','5') else 'in'
        if pt == 'in' and daily_punches[a.date]['in'] is None:
            daily_punches[a.date]['in'] = a
        elif pt == 'out':
            daily_punches[a.date]['out'] = a

    weeks = []
    for week in calendar.monthcalendar(year, month):
        reordered = [week[6]] + week[:6]
        row = []
        for day_num in reordered:
            if day_num == 0:
                row.append(None)
                continue
            d         = date(year, month, day_num)
            is_sunday = d.weekday() == 6
            is_future = d > today
            day_data  = daily_punches.get(d, {})
            att_in    = day_data.get('in')
            att_out   = day_data.get('out')
            hours_worked = None
            if att_in and att_out:
                from datetime import datetime as dt_cls
                dt_in    = dt_cls.combine(d, att_in.time)
                dt_out   = dt_cls.combine(d, att_out.time)
                hours_worked = round((dt_out - dt_in).seconds / 3600, 1)

            row.append({
                'day':          day_num,
                'date':         d,
                'is_sunday':    is_sunday,
                'is_future':    is_future,
                'is_present':   att_in is not None and not is_sunday,
                'is_absent':    att_in is None and not is_sunday and not is_future,
                'att_in':       att_in,
                'att_out':      att_out,
                'hours_worked': hours_worked,
            })
        weeks.append(row)

    total_working = sum(
        1 for dn in range(1, calendar.monthrange(year, month)[1] + 1)
        if date(year, month, dn).weekday() != 6 and date(year, month, dn) <= today
    )
    present = sum(1 for d in daily_punches if d.weekday() != 6 and d <= today)
    pct     = round(present / total_working * 100) if total_working else 0

    return {
        'weeks':              weeks,
        'month_name':         calendar.month_name[month],
        'year':               year,
        'month':              month,
        'total_working_days': total_working,
        'present_days':       present,
        'absent_days':        total_working - present,
        'attendance_pct':     pct,
    }
"""def _build_staff_calendar(staff, year, month):
    today = date.today()
    # Deduplicate: prefer wifi_verified row if multiple exist per date
    records = {}
    for a in Attendance.objects.filter(staff=staff, date__year=year, date__month=month):
        if a.date not in records :#bio
            records[a.date] = a

    weeks = []
    for week in calendar.monthcalendar(year, month):
        reordered = [week[6]] + week[:6]
        row = []
        for day_num in reordered:
            if day_num == 0:
                row.append(None)
                continue
            d         = date(year, month, day_num)
            is_sunday = d.weekday() == 6
            is_future = d > today
            att       = records.get(d)
            row.append({
                'day':        day_num,
                'date':       d,
                'is_sunday':  is_sunday,
                'is_future':  is_future,
                'is_present': att is not None and not is_sunday,
                'is_absent':  att is None and not is_sunday and not is_future,
                'att':        att,
            })
        weeks.append(row)

    total_working = sum(
        1 for dn in range(1, calendar.monthrange(year, month)[1] + 1)
        if date(year, month, dn).weekday() != 6 and date(year, month, dn) <= today
    )
    present = len([d for d in records if d.weekday() != 6 and d <= today])
    pct     = round(present / total_working * 100) if total_working else 0

    return {
        'weeks':              weeks,
        'month_name':         calendar.month_name[month],
        'year':               year,
        'month':              month,
        'total_working_days': total_working,
        'present_days':       present,
        'absent_days':        total_working - present,
        'attendance_pct':     pct,
    }

"""
# ── STUDENT CALENDAR HELPER ───────────────────
def _build_student_calendar(student, year, month):
    today = date.today()
    records = {
        a.date: a
        for a in StudentAttendance.objects.filter(
            student=student, date__year=year, date__month=month
        )
    }

    weeks = []
    for week in calendar.monthcalendar(year, month):
        reordered = [week[6]] + week[:6] 
        row = []
        for day_num in reordered:
            if day_num == 0:
                row.append(None)
                continue
            d         = date(year, month, day_num)
            is_sunday = d.weekday() == 6
            is_future = d > today
            att       = records.get(d)
            row.append({
                'day':        day_num,
                'date':       d,
                'is_sunday':  is_sunday,
                'is_future':  is_future,
                'is_present': att is not None and att.status is True,
                'is_absent':  att is not None and att.status is False,
                'unmarked':   att is None and not is_sunday and not is_future,
            })
        weeks.append(row)

    working = sum(
        1 for dn in range(1, calendar.monthrange(year, month)[1] + 1)
        if date(year, month, dn).weekday() != 6 and date(year, month, dn) <= today
    )
    present = sum(1 for a in records.values() if a.status is True)
    absent  = sum(1 for a in records.values() if a.status is False)
    pct     = round(present / working * 100) if working else 0

    return {
        'cal_weeks':    weeks,
        'month_name':   calendar.month_name[month],
        'year':         year,
        'month':        month,
        'working_days': working,
        'present_days': present,
        'absent_days':  absent,
        'pct':          pct,
    }


# ── STAFF ATTENDANCE CALENDAR — ADMIN ────────
@staff_member_required
def admin_staff_attendance_calendar(request, staff_id):
    staff = get_object_or_404(Staff, pk=staff_id)
    today = date.today()

    leave_obj, _ = StaffLeave.objects.get_or_create(staff=staff, defaults={'join_date': today})
    _credit_monthly_leave(leave_obj, today)

    year  = int(request.GET.get('year',  today.year))
    month = int(request.GET.get('month', today.month))

    if request.method == 'POST':
        action     = request.POST.get('action')
        date_str   = request.POST.get('date')
        leave_type = request.POST.get('leave_type', 'absent')
        try:
            target = datetime.strptime(date_str, '%Y-%m-%d').date()
            if target.weekday() == 6:
                messages.error(request, "Cannot mark attendance on Sunday.")
            elif action == 'mark_present':
                # Delete all rows for this date then create one clean row
                Attendance.objects.filter(staff=staff, date=target).delete()
                Attendance.objects.create(staff=staff, date=target,time=datetime.now().time(),source="admin")#bio
                StaffLeaveUsage.objects.filter(staff=staff, date=target).delete()
                messages.success(request, f"Marked present for {target}.")
            elif action == 'mark_absent':
                Attendance.objects.filter(staff=staff, date=target).delete()
                StaffLeaveUsage.objects.update_or_create(
                    staff=staff, date=target,
                    defaults={'leave_type': leave_type}
                )
                if leave_type == 'paid' and leave_obj.leave_balance >= 1:
                    leave_obj.leave_balance -= 1
                    leave_obj.leave_used    += 1
                    leave_obj.save()
                    messages.success(request, f"Marked paid leave for {target}.")
                else:
                    messages.success(request, f"Marked absent for {target}.")
        except Exception as e:
            messages.error(request, f"Error: {e}")
        return redirect(f"{request.path}?year={year}&month={month}")

    cal_data = _build_staff_calendar(staff, year, month)
    prev     = date(year, month, 1) - relativedelta(months=1)
    nxt      = date(year, month, 1) + relativedelta(months=1)

    summaries = [_build_staff_calendar(staff, (date(today.year, today.month, 1) - relativedelta(months=d)).year,
                                              (date(today.year, today.month, 1) - relativedelta(months=d)).month)
                 for d in range(2, 0, -1)]

    unlock_date    = leave_obj.join_date + relativedelta(months=3)
    leave_unlocked = today >= unlock_date

    return render(request, 'staff_attendance_calendar.html', {
        'staff':          staff,
        'cal':            cal_data,
        'prev_year':      prev.year,   'prev_month':  prev.month,
        'next_year':      nxt.year,    'next_month':  nxt.month,
        'leave_obj':      leave_obj,   'leave_unlocked': leave_unlocked,
        'unlock_date':    unlock_date, 'summaries':   summaries,
        'today':          today,
    })


# ── STAFF OWN ATTENDANCE ──────────────────────
@login_required
def staff_own_attendance(request):
    staff = get_object_or_404(Staff, user=request.user)

    is_placement = staff.courses.filter(course_name__iexact="placement").exists()

    today = date.today()

    leave_obj, _ = StaffLeave.objects.get_or_create(staff=staff, defaults={'join_date': today})
    _credit_monthly_leave(leave_obj, today)

    year  = int(request.GET.get('year',  today.year))
    month = int(request.GET.get('month', today.month))
    cal_data = _build_staff_calendar(staff, year, month)
    prev     = date(year, month, 1) - relativedelta(months=1)
    nxt      = date(year, month, 1) + relativedelta(months=1)

    unlock_date    = leave_obj.join_date + relativedelta(months=3)
    leave_unlocked = today >= unlock_date

    return render(request, 'staff_attendance_calendar.html', {
        'staff':          staff,
        'cal':            cal_data,
        'prev_year':      prev.year,   'prev_month':  prev.month,
        'next_year':      nxt.year,    'next_month':  nxt.month,
        'leave_obj':      leave_obj,   'leave_unlocked': leave_unlocked,
        'unlock_date':    unlock_date, 'summaries':   [],
        'today':          today,       'readonly':    True,
        'is_placement': is_placement
    })


# ── STUDENT ATTENDANCE CALENDAR — ADMIN ──────
@staff_member_required
def admin_student_attendance_calendar(request, student_id):
    student = get_object_or_404(Student, pk=student_id)
    today   = date.today()

    year  = int(request.GET.get('year',  today.year))
    month = int(request.GET.get('month', today.month))

    if request.method == 'POST':
        action   = request.POST.get('action')
        date_str = request.POST.get('date')
        try:
            target = datetime.strptime(date_str, '%Y-%m-%d').date()
            if target.weekday() == 6:
                messages.error(request, "Cannot mark attendance on Sunday.")
            elif action == 'mark_present':
                att, created = StudentAttendance.objects.get_or_create(
                    student=student, date=target, defaults={'status': True}
                )
                if not created:
                    att.status = True
                    att.save()
                messages.success(request, f"Marked present for {target}.")
            elif action == 'mark_absent':
                att, created = StudentAttendance.objects.get_or_create(
                    student=student, date=target, defaults={'status': False}
                )
                if not created:
                    att.status = False
                    att.save()
                messages.success(request, f"Marked absent for {target}.")
        except Exception as e:
            messages.error(request, f"Error: {e}")
        return redirect(f"{request.path}?year={year}&month={month}")

    cal = _build_student_calendar(student, year, month)
    prev = date(year, month, 1) - relativedelta(months=1)
    nxt  = date(year, month, 1) + relativedelta(months=1)

    summaries = []
    for delta in range(2, 0, -1):
        d2 = date(today.year, today.month, 1) - relativedelta(months=delta)
        c2 = _build_student_calendar(student, d2.year, d2.month)
        summaries.append({
            'month_name':         c2['month_name'],
            'year':               c2['year'],
            'present_days':       c2['present_days'],
            'total_working_days': c2['working_days'],
            'attendance_pct':     c2['pct'],
        })

    return render(request, 'student_attendance_calendar.html', {
        'student':      student,
        'cal_weeks':    cal['cal_weeks'],
        'month_name':   cal['month_name'],
        'year':         cal['year'],    'month':       cal['month'],
        'working_days': cal['working_days'],
        'present_days': cal['present_days'],
        'absent_days':  cal['absent_days'],
        'pct':          cal['pct'],
        'prev_year':    prev.year,      'prev_month':  prev.month,
        'next_year':    nxt.year,       'next_month':  nxt.month,
        'summaries':    summaries,      'today':       today,
    })


# ── ADMIN STUDENTS OVERVIEW ───────────────────
@staff_member_required
def admin_students_overview(request):
    staff_filter  = request.GET.get('staff',  '')
    course_filter = request.GET.get('course', '')

    qs = Student.objects.select_related('course', 'staff', 'batch').all()
    if staff_filter:
        qs = qs.filter(staff__staff_id=staff_filter)
    if course_filter:
        qs = qs.filter(course__course_id=course_filter)

    student_data = []
    for student in qs:
        total     = CourseTopic.objects.filter(course=student.course).count()
        completed = StudentTopicProgress.objects.filter(student=student, end_date__isnull=False).count()
        student_data.append({
            'student':      student,
            'total_topics': total,
            'completed':    completed,
            'pct':          round(completed / total * 100) if total else 0,
        })

    return render(request, 'admin_students_overview.html', {
        'student_data':  student_data,
        'all_staff':     Staff.objects.all(),
        'all_courses':   Course.objects.all(),
        'staff_filter':  staff_filter,
        'course_filter': course_filter,
    })


# ── ADMIN STUDENT PROGRESS DETAIL ────────────
@staff_member_required
def admin_student_progress_detail(request, student_id):
    student = get_object_or_404(Student, pk=student_id)
    topics  = CourseTopic.objects.filter(course=student.course).order_by('topic_id')
    progress_map = {p.topic_id: p for p in StudentTopicProgress.objects.filter(student=student)}

    total     = topics.count()
    completed = sum(1 for t in topics if progress_map.get(t.pk) and progress_map[t.pk].end_date)
    pct       = round(completed / total * 100) if total else 0

    modules = {}
    for topic in topics:
        p = progress_map.get(topic.pk)
        modules.setdefault(topic.module_name, []).append({
            'topic': topic, 'progress': p, 'done': bool(p and p.end_date)
        })

    return render(request, 'admin_student_progress_detail.html', {
        'student':     student,
        'modules':     modules,
        'total':       total,
        'completed':   completed,
        'pct':         pct,
        'batch_id':    student.batch_id if student.batch else None,
        'back_params': request.GET.urlencode(),
    })

@csrf_exempt
def iclock_data(request):
    if request.method == "GET":
        return HttpResponse("OK")

    if request.method == "POST":
        raw   = request.body.decode('utf-8', errors='ignore').strip()
        sn    = request.GET.get("SN",    "UNKNOWN").strip()
        table = request.GET.get("table", "").strip()

        if table != "ATTLOG":
            return HttpResponse("OK")

        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue

            user_id     = parts[0].strip()
            check_time  = parts[1].strip()
            verify_code = parts[2].strip() if len(parts) > 2 else "0"
            status_code = parts[3].strip() if len(parts) > 3 else "0"  # ← in/out signal

            punch_type = 'out' if status_code in ('1', '5') else 'in'
            logger.warning(f"parts={parts}")

            try:
                staff = Staff.objects.get(staff_id=user_id)
            except Staff.DoesNotExist:
                logger.warning(f"[Biometric] Unknown UserID: {user_id}")
                continue

            try:
                dt = datetime.strptime(check_time, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                logger.error(f"[Biometric] Bad timestamp: {check_time}")
                continue

            obj, created = Attendance.objects.get_or_create(
                staff=staff,
                date=dt.date(),
                time=dt.time(),
                source="biometric",
                defaults={
                    "device_sn":   sn,
                    "verify_code": verify_code,
                }
            )
            logger.info(
                f"[Biometric] {'NEW' if created else 'DUP'} | "
                f"Staff: {staff.staff_name} | {punch_type.upper()} | Time: {dt}"
            )

        return HttpResponse("OK")

    return HttpResponse("FAILED")


@login_required
def add_company(request):
    staff = getattr(request.user, 'staff', None)

    if not staff:
        return redirect('home')

    if request.method == "POST":
        CompanyInterview.objects.create(
            company_name=request.POST['company_name'],
            role=request.POST['role'],
            interview_date=request.POST.get('interview_date','').strip() or None,
            description=request.POST['description'],
            created_by=staff,
            status="ongoing",
            experience=request.POST.get("experience"),
            skills=request.POST.get("skills"),
            location=request.POST.get("location"),
            salary=request.POST.get("salary"),
        )
        return redirect('placement_dashboard')

    return redirect('placement_dashboard')

@login_required
def placement_dashboard(request):
    staff = getattr(request.user, 'staff', None)

    if not staff:
        return redirect('home')

    # 🔒 only placement staff allowed
    if not staff.courses.filter(course_name__iexact="placement").exists():
        return redirect('get_batches')

    # SHOW ALL COMPANIES (NO FILTER)
    ongoing = CompanyInterview.objects.filter(
        status="ongoing"
    ).order_by("interview_date")

    completed = CompanyInterview.objects.filter(
        status="completed"
    ).order_by("-interview_date")

    return render(request, "placement_dashboard.html", {
        "ongoing": ongoing,
        "completed": completed,
        "staff": staff   # for showing name on top
    })

@login_required
def complete_interview(request, id):
    company = get_object_or_404(CompanyInterview, id=id)
    company.status = "completed"
    company.save()
    return redirect('placement_dashboard')

#studentProgressDashboardAdmin
def update_single_student_progress(student):
    topics_count = CourseTopic.objects.filter(
    course=student.course).count()

    finished_topics = StudentTopicProgress.objects.filter(
        student=student,
        end_date__isnull=False
    ).count()

    print("DEBUG:", student.student_id, topics_count, finished_topics)

    StudentProgressDashboard.objects.update_or_create(
        student=student,
        defaults={
            "total_topics": topics_count,
            "finished_topics": finished_topics
        }
    )


def studentprogress_dashboard():
    from django.db.models import Count,Q
    students = Student.objects.select_related("course", "staff").prefetch_related("course__topics").annotate(
    finished_topics=Count('studenttopicprogress', filter=Q(studenttopicprogress__end_date__isnull=False)))

    for s in students:
       topics_count = s.course.topics.count()
       finished_topics = s.finished_topics
       StudentProgressDashboard.objects.update_or_create(
            student=s,
            defaults={
                "total_topics": topics_count,
                "finished_topics": finished_topics
            })
    print(f"{topics_count}, {finished_topics}, {s.student_name}")
    

def dashboard_view(request):

    dashboards = StudentProgressDashboard.objects.select_related(
        "student__staff", "student__course"
    )

    staffs = Staff.objects.all()
    courses = Course.objects.all()

    return render(request, "dashboard.html", {
        "dashboards": dashboards,
        "staffs": staffs,
        "courses": courses,
    })

@login_required
@require_POST
def toggle_placement(request, student_id):
    student = get_object_or_404(Student, pk=student_id)

    dashboard, _ = StudentProgressDashboard.objects.get_or_create(student=student)

    # Toggle placement
    dashboard.placed = not dashboard.placed
    dashboard.save(update_fields=["placed"])

    return redirect(request.META.get('HTTP_REFERER', '/'))

@login_required
@require_POST
def toggle_ready(request, student_id):
    student = get_object_or_404(Student, pk=student_id)

    dashboard, _ = StudentProgressDashboard.objects.get_or_create(student=student)

    # Toggle ready status
    dashboard.ready_to_placement = not dashboard.ready_to_placement
    dashboard.save(update_fields=["ready_to_placement"])

    return redirect(request.META.get('HTTP_REFERER', '/'))


@login_required
def view_applications(request, company_id):
    company = get_object_or_404(CompanyInterview, id=company_id)

    applications = JobApplication.objects.filter(company=company)

    return render(request, "view_applications.html", {
        "company": company,
        "applications": applications
    })

@login_required
def download_resume(request, app_id):
    app = get_object_or_404(JobApplication, id=app_id)

    # 🔥 HANDLE BOTH CASES
    if hasattr(app.resume, 'path'):
        file_path = app.resume.path   # FileField case
    else:
        file_path = app.resume        # CharField case

    if not os.path.exists(file_path):
        return HttpResponse(f"File not found: {file_path}")

    return FileResponse(
        open(file_path, 'rb'),
        as_attachment=True,
        filename=os.path.basename(file_path)
    )

def api_jobs(request):
    jobs = CompanyInterview.objects.filter(status="ongoing")

    data = []
    for job in jobs:
        applied = False

        if request.user.is_authenticated:
            student = Student.objects.filter(student_email=request.user.username).first()
            if student:
                applied = JobApplication.objects.filter(
                    student=student,
                    company=job
                ).exists()

        data.append({
            "id": job.id,
            "company_name": job.company_name,
            "role": job.role,
            "interview_date": str(job.interview_date),
            "experience": job.experience,
            "applied": applied,
            "location": job.location,
            "salary": job.salary,
        })

    return JsonResponse(data, safe=False)

def website(request):
    return render(request, "website.html")


RESUME_DIR = r"D:\placement_resumes"

def apply_job(request, company_id):
    company = get_object_or_404(CompanyInterview, id=company_id)

    if request.method == "POST":
        name = request.POST.get("name")
        email = request.POST.get("email")
        phone = request.POST.get("phone")
        course_name = request.POST.get("course")
        resume = request.FILES.get("resume")

        if not resume:
            return render(request, "apply_job.html", {
                "company": company,
                "error": "Upload resume!"
            })

        # create folder
        if not os.path.exists(RESUME_DIR):
            os.makedirs(RESUME_DIR)

        # unique file
        filename = str(uuid.uuid4()) + "_" + resume.name
        file_path = os.path.join(RESUME_DIR, filename)

        # save file
        with open(file_path, 'wb+') as f:
            for chunk in resume.chunks():
                f.write(chunk)

        # course
        # course = Course.objects.filter(course_name__iexact=course_name).first()

        # if not course:
        #     course = Course.objects.create(course_name=course_name)
            
        # student
        # student, _ = Student.objects.get_or_create(
        #     student_email=email,
        #     defaults={
        #         "student_name": name,
        #         "student_contact": phone,
        #         "join_date": date.today(),
        #         "course": course_name
        #     }
        # )

        # duplicate check
        # if JobApplication.objects.filter(student=student, company=company).exists():
        #     return render(request, "apply_job.html", {
        #         "company": company,
        #         "error": "Already applied!"
        #     })

        # save DB
        JobApplication.objects.create(
            student=name,
            company=company,
            resume=file_path,
            email=email,
            phoneNumber=phone,
            course=course_name
        )

        return render(request, "apply_job.html", {
            "company": company,
            "success": "Applied successfully 🎉"
        })

        return redirect("placement_page")

    return render(request, "apply_job.html", {"company": company})

def placement_page(request):
    jobs = CompanyInterview.objects.filter(status="ongoing").order_by("interview_date")

    return render(request, "placement.html", {
        "jobs": jobs
    })


@login_required
def edit_company(request, id):
    company = get_object_or_404(CompanyInterview, id=id)
    if request.method == "POST":
        company.company_name   = request.POST.get("company_name", company.company_name)
        company.role           = request.POST.get("role", company.role)
        company.interview_date = request.POST.get("interview_date") or None
        company.experience     = request.POST.get("experience")
        company.location       = request.POST.get("location")
        company.salary         = request.POST.get("salary")
        company.skills         = request.POST.get("skills")
        company.description    = request.POST.get("description")
        company.save()
    return redirect("placement_dashboard")