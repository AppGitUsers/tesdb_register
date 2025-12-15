from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from .models import Student, StudentTopicProgress, Staff, CourseTopic , Attendance , StudentAttendance ,Batch
from django.contrib import messages
from django.forms import modelformset_factory
from django import forms
from django.utils.timezone import now,localdate,datetime
from django.utils import timezone
from django.urls import reverse
from datetime import date
import logging
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)


def home(request):
    return render(request, 'home.html')

def register_staff(request):
    if request.method=="POST":
        username = request.POST.get('username')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        if User.objects.filter(username=username):
            messages.error(request,'User name already exist!!')
            return render(request,'register_staff.html')
        
        if password != confirm_password:
            messages.error(request,'password not match ')
            return render(request,'register_staff.html')
        
        if len(password) <=8:
            messages.error(request,'Password must be at least 8 characters long.\n' \
            'Include both uppercase and lowercase letters, \n' \
            'numbers, and special characters.')
            return render(request,'register_staff.html')
        user = User.objects.create_user(username=username,password=password)
        user.save()
        messages.success(request,'Registered successfully!!')
        return redirect('staff_login')
  
    return render(request,'register_staff.html')


@login_required
def student_detail(request, student_id,batch_id):
    student = get_object_or_404(Student, pk=student_id)

    print("student :",student)
    #  Only allow staff to see their own students
    if hasattr(request.user, 'staff'):
        if student.staff != request.user.staff:
            return redirect('home')

    #  Fetch all topics for the student's course
    # topics = CourseTopic.objects.filter(course=student.course).order_by('module_name', 'topic_name')
    topics = CourseTopic.objects.filter(course=student.course).order_by('topic_id')


    #  Get progress for each topic (or None if not yet added)
    progress_dict = {
        p.topic_id: p for p in StudentTopicProgress.objects.filter(student=student)
    }

    # Build a list with topic + progress (if exists)
    topic_progress_list = []
    for topic in topics:
        topic_progress_list.append({
            "topic": topic,
            "progress": progress_dict.get(topic.pk)
        })

    return render(request, 'student_detail.html', {
        'student': student,
        'topic_progress_list': topic_progress_list,
        'batch_id': batch_id,
    })

@login_required
def student_list(request,batch_id):
    staff = get_object_or_404(Staff, user=request.user)
    batch=get_object_or_404(Batch, pk=batch_id, staff=staff)
    students = Student.objects.filter(staff=staff,batch=batch)
    batches=Batch.objects.filter(staff=staff)

    today = localdate()
    attendance=Attendance.objects.filter(staff=staff,date=today).last()
    print(attendance)
    if request.method == "POST":
        student_id = request.POST.get('student_id')
        new_batch_id = request.POST.get('batch')
        student = get_object_or_404(Student, pk=student_id, staff=staff)
        if new_batch_id:
            new_batch = get_object_or_404(Batch, pk=new_batch_id, staff=staff)
            student.batch = new_batch

        # Update batch and mode
        # batch = request.POST.get('batch')
        mode = request.POST.get('mode')

        # if batch in ['True', 'False']:
        #     student.batch = True if batch == 'True' else False
        if mode in ['True', 'False']:
            student.mode = True if mode == 'True' else False

        student.save()
        return redirect('student_list', batch_id=batch_id)
    all_batches = Batch.objects.filter(staff=staff)
    return render(request, 'student_list.html', {'students': students , 'attendance':attendance,'batch':batch,'all_batches':all_batches,'batches':batches,})


@login_required
def add_progress(request, student_id,batch_id):
    staff = get_object_or_404(Staff, user=request.user)
    student = get_object_or_404(Student, pk=student_id, staff=staff)
    batch = get_object_or_404(Batch, pk=batch_id)
    # Ensure all topics exist for this student
    topics = CourseTopic.objects.filter(course=student.course).order_by('topic_id')
    for topic in topics:
        StudentTopicProgress.objects.get_or_create(
            student=student,
            topic=topic
        )

    class ProgressForm(forms.ModelForm):
        class Meta:
            model = StudentTopicProgress
            fields = ('start_date', 'end_date', 'marks')
            widgets = {
                'start_date': forms.DateInput(attrs={'type': 'date'}),
                'end_date': forms.DateInput(attrs={'type': 'date'}),
            }

    ProgressFormSet = modelformset_factory(
        StudentTopicProgress,
        form=ProgressForm,
        extra=0
    )

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
            return redirect('student_detail', student_id=student.pk,batch_id=batch.pk)
        else:
            print("Formset errors:", formset.errors)
            print("Non-form errors:", formset.non_form_errors())

    else:
        formset = ProgressFormSet(queryset=queryset)

    topic_form_pairs = list(zip(formset.forms, topics))

    return render(request, 'add_progress.html', {
        'student': student,
        'formset': formset,
        'topic_form_pairs': topic_form_pairs,
        'batch_id': batch.pk,
    })



def staff_login(request):
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            #  Redirect staff to student batch list (not back to home)
            if hasattr(user, 'staff'):
                return redirect('get_batches')
            return redirect('home')
        else:
            messages.error(request, "Invalid username or password.")
    return render(request, 'staff_login.html')


@login_required
def add_batch(request):
    staff=get_object_or_404(Staff,user=request.user)
    if request.method=="POST":
        batch_name=request.POST["batch_name"]
        start_time=request.POST["start_time"]
        end_time=request.POST["end_time"]
        if not batch_name or not start_time or not end_time:
            messages.error(request, "All fields are required.")
            return redirect("add_batch")
        if Batch.objects.filter(staff=staff, batch_name=batch_name).exists():
            messages.error(request, "!!!Batch with this name already exists.")
            return redirect("add_batch")

        Batch.objects.create(
            staff=staff,
            batch_name=batch_name,
            start_time=start_time,
            end_time=end_time
        )

        messages.success(request,"NEW BATCH ADDED SCCESSFULLY")
        return redirect("get_batches")
    
    return render(request,"add_batch.html")

@login_required
def edit_batch(request,batch_id):
    staff=get_object_or_404(Staff,user=request.user)
    batch=get_object_or_404(Batch,pk=batch_id,staff=staff)
    if request.method=="POST":
        batch_name=request.POST["batch_name"]
        start_time=request.POST["start_time"]
        end_time=request.POST["end_time"]
        if not batch_name or not start_time or not end_time:
            messages.error(request, "All fields are required.")
            return redirect("edit_batch",batch_id=batch_id)
        
        batch.batch_name=batch_name
        batch.start_time=start_time
        batch.end_time=end_time
        batch.save()
        messages.success(request,"BATCH UPDATED SCCESSFULLY")
        return redirect('get_batches')
    return render(request,"add_batch.html",{"batch":batch})


@login_required
def delete_batch(request, batch_id):
    staff = get_object_or_404(Staff, user=request.user)
    batch = get_object_or_404(Batch, pk=batch_id, staff=staff)


    if request.method == "POST":
        student_count=Student.objects.filter(batch=batch).count()
        if student_count>0:
            messages.error(request, "Cannot delete batch with assigned students.")
            return redirect('get_batches')
        batch.delete()
        messages.success(request, "Batch deleted successfully.")
        return redirect('get_batches')

@login_required
def mark_student_attendance(request,batch_id):
    staff = get_object_or_404(Staff, user=request.user)
    batch=get_object_or_404(Batch, pk=batch_id, staff=staff)
    students = Student.objects.filter(staff=staff,batch=batch)
    today = timezone.now().date()

    # --- Get the selected date (POST first, then GET) ---
    date_str = request.POST.get("date") or request.GET.get("date")
    if date_str:
        try:
            selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            selected_date = today
    else:
        selected_date = today

    # Prevent future dates
    if selected_date > today:
        selected_date = today
    logger.info(f"Selected date for attendance: {selected_date}")

    # --- Save attendance if POST ---
    if request.method == "POST":
        for student in students:
            status = request.POST.get(f"status_{student.student_id}")
            if status is not None:
                status_bool = True if status == "present" else False
                attendance, created = StudentAttendance.objects.get_or_create(
                    student=student,
                    date=selected_date,
                    defaults={"status": status_bool}
                )
                print("attendance : ",attendance, "created : ",created)
                if not created:
                    attendance.status = status_bool
                    attendance.save()
                    print("attendance : ",attendance, "created : ",created)
        # Redirect back to the same selected date
        return redirect(f"{reverse('student_attendance', args=[batch.batch_id])}?date={selected_date.strftime('%Y-%m-%d')}")

    # --- Load attendance for selected date ---
    attendance_records = {
        att.student_id: att
        for att in StudentAttendance.objects.filter(date=selected_date, student__in=students)
    }

    return render(request, "student_attendance.html", {
        "students": students,
        "attendance_records": attendance_records,
        "today": today.strftime("%Y-%m-%d"),
        "selected_date": selected_date.strftime("%Y-%m-%d"),
        "batch": batch,
    })

@login_required
def getBatches(request):
    staff= get_object_or_404(Staff, user=request.user)
    batches = Batch.objects.filter(staff=staff).order_by('start_time')
    return render(request, 'batch.html', {'batches': batches,'staff':staff})


    # return render(request, 'confirm_delete.html', {'batch': batch})

def staff_logout(request):
    logout(request)
    return redirect('staff_login')


# @require_GET
# @login_required
# def get_staffs_json(request):
#     """Return staff list for a given course (used by JS)"""
#     course_id = request.GET.get("course_id")
#     if not course_id:
#         return JsonResponse([], safe=False)

#     staffs = Staff.objects.filter(course__course_id=course_id).values("staff_id", "staff_name")
#     data = [{"id": s["staff_id"], "name": s["staff_name"]} for s in staffs]
#     return JsonResponse(data, safe=False)


# @require_GET
# @login_required
# def get_batches_json(request):
#     """Return batch list for a given staff (used by JS)"""
#     staff_id = request.GET.get("staff_id")
#     if not staff_id:
#         return JsonResponse([], safe=False)

#     batches = Batch.objects.filter(staff__staff_id=staff_id).values("batch_id", "batch_name")
#     data = [{"id": b["batch_id"], "name": b["batch_name"]} for b in batches]
#     return JsonResponse(data, safe=False)
