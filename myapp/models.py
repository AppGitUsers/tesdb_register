from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator


# Professional mobile number validation (India)
mobile_validator = RegexValidator(
    regex=r'^[6-9]\d{9}$',
    message="Enter a valid 10-digit mobile number starting with 6-9."
)

# Create your models here.
class Staff(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    staff_name =models.CharField(max_length=100)
    contact=models.CharField(max_length=10,validators=[mobile_validator],blank=True)
    staff_id = models.AutoField(primary_key=True)
    staff_email = models.EmailField(unique=True)
    courses = models.ManyToManyField("Course", related_name="staffs")
        
    #bio
    def __str__(self):
        return self.staff_name

class Course(models.Model):
    course_id = models.AutoField(primary_key=True)
    course_name = models.CharField(max_length=100,unique=True)
                
    def __str__(self):
        return self.course_name
    def save(self,*args,**kwargs):
        #print(self.course_name)
        if self.course_name:
            self.course_name=self.course_name.capitalize()
            #print(self.course_name)
        super().save(*args,**kwargs)

class Student(models.Model):
    student_id = models.AutoField(primary_key=True)
    student_name = models.CharField(max_length=100)
    join_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='students')
    staff = models.ForeignKey(Staff, on_delete=models.SET_NULL,null=True,blank=True, related_name='students')
    student_email = models.EmailField(unique=True)
    student_contact = models.CharField(max_length=20, blank=True)
    # BATCH_CHOICES = [
    #     (True, 'Morning'),
    #     (F`alse, 'Afternoon'),
    # ]
    # batch = models.BooleanField(choices=BATCH_CHOICES, default=True)
    
    batch = models.ForeignKey("Batch", on_delete=models.SET_NULL, null=True, blank=True, related_name="students")

    MODE_CHOICES = [
        (True, 'Offline'),
        (False, 'Online'),
    ]
    mode = models.BooleanField(choices=MODE_CHOICES, default=True)


    def __str__(self):
        course_name = self.course.course_name if self.course else "No Course"
        staff_name = self.staff.staff_name if self.staff else "Unassigned"
        return f"{self.student_name} ({course_name} - {staff_name})"


class CourseTopic(models.Model):
    topic_id = models.AutoField(primary_key=True)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='topics')
    module_name = models.CharField(max_length=100)
    topic_name = models.CharField(max_length=100)

    class Meta:
        unique_together = ('course', 'module_name', 'topic_name')
        ordering = ('course','module_name','topic_name')
    def __str__(self):
        return f"{self.module_name} - {self.topic_name}"
    
    def save(self,*args,**kwargs):
        print(self.module_name)
        if self.module_name and self.topic_name:
            self.module_name=self.module_name.capitalize()
            self.topic_name=self.topic_name.capitalize()
            print(self.module_name)
        super().save(*args,**kwargs)

class StudentTopicProgress(models.Model):
    id = models.AutoField(primary_key=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='progress')
    topic = models.ForeignKey(CourseTopic, on_delete=models.CASCADE, related_name='progress')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    marks = models.IntegerField(null=True, blank=True)
    sign = models.CharField(max_length=100, help_text="Staff full name")

    class Meta:
        unique_together = ('student', 'topic')

    def __str__(self):
        return f"{self.student.student_name} - {self.topic.topic_name}"

    # Add Date Validation
    def clean(self):
        # If end_date is provided but start_date is empty
        if self.end_date and not self.start_date:
            raise ValidationError("Start Date is required when End Date is filled.")

        # If both dates exist → check order
        if self.start_date and self.end_date:
            if self.start_date > self.end_date:
                raise ValidationError("Start Date cannot be greater than End Date.")


"""
class Attendance(models.Model):
    staff = models.ForeignKey("Staff", on_delete=models.CASCADE, related_name="attendances")
    date = models.DateField(default=timezone.now)
    time = models.TimeField(null=True,blank=True)
#bio     #wifi_verified = models.BooleanField(default=False)  # was it from correct WiFi?
    source = models.CharField(
        max_length=20,
        choices=[
            ("biometric", "Biometric"),
            ("manual", "Manual Entry"),
            ("admin", "Admin Entry"),
        ],
        default="biometric"
    )

    device_sn = models.CharField(max_length=50, null=True, blank=True)
    verify_code = models.CharField(max_length=10, null=True, blank=True)

    created_at = models.DateTimeField(null=True,blank=True)
#bio
    class Meta:
#bio
        unique_together = ('staff', 'date')  # only one attendance per staff per day

    def __str__(self):
        return f"{self.staff.staff_name} - {self.date} "
`"""
class Attendance(models.Model):
    staff       = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name="attendances")
    date        = models.DateField()
    time        = models.TimeField(null=True,blank=True)
    source      = models.CharField(max_length=20, default='biometric')
    device_sn   = models.CharField(max_length=50,null=True, blank=True)
    verify_code = models.CharField(max_length=10, null=True,blank=True)
    created_at  = models.DateTimeField(null=True, blank=True)  # keep nullable, matches existing DB
    class Meta:
        ordering = ['date', 'time']
    def __str__(self):
        return f"{self.staff.staff_name} - {self.date}"
class StudentAttendance(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField(default=timezone.now)
    time = models.TimeField(null=True,blank=True)
    STATUS_CHOICES = [
        (True, 'Present'),
        (False, 'Absent'),
    ]
    status=models.BooleanField(choices=STATUS_CHOICES, null=True,blank=True)  # True for Present, False for Absent

    class Meta:
        unique_together = ('student', 'date')  # only one attendance per student per day

    def __str__(self):
        return f"{self.student.student_name} - {self.date}"


class Batch(models.Model):
    batch_id = models.AutoField(primary_key=True)
    staff = models.ForeignKey("Staff", on_delete=models.CASCADE, related_name="batches")
    batch_name = models.CharField(max_length=50, help_text="Example: Morning Batch")
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        unique_together = ('staff', 'batch_name')
        ordering = ['start_time']

    def __str__(self):
        return f"{self.batch_name} ({self.start_time.strftime('%I:%M %p')} - {self.end_time.strftime('%I:%M %p')})"

    def clean(self):
        # Validate time order
        if self.start_time and self.end_time:
            if self.start_time >= self.end_time:
                raise ValidationError("End Time must be later than Start Time.")
            


class StaffCourseProgress(models.Model):
    """Tracks which course topics a staff member has self-studied and marked complete."""
    id = models.AutoField(primary_key=True)
    staff = models.ForeignKey("Staff", on_delete=models.CASCADE, related_name="course_progress")
    topic = models.ForeignKey("CourseTopic", on_delete=models.CASCADE, related_name="staff_progress")
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('staff', 'topic')

    def __str__(self):
        status = "✓" if self.completed else "○"
        return f"{status} {self.staff.staff_name} — {self.topic.topic_name}"
    

# ── ADD THESE TO THE BOTTOM of your existing models.py ───────────────────────
# (Keep all existing models above, just paste these at the end)

class StaffLeave(models.Model):
    """
    Paid-leave balance per staff.
    - Unlocked after 3 calendar months from join_date.
    - 1 day credited every month after unlock.
    - Credit is applied lazily when the staff attendance page is visited.
    """
    staff         = models.OneToOneField("Staff", on_delete=models.CASCADE, related_name="leave")
    join_date     = models.DateField(help_text="Date this staff member started")
    leave_balance = models.DecimalField(max_digits=6, decimal_places=1, default=0)
    leave_used    = models.DecimalField(max_digits=6, decimal_places=1, default=0)
    last_credited = models.DateField(null=True, blank=True,
                                     help_text="Last month-start on which 1 day was credited")

    def __str__(self):
        return f"{self.staff.staff_name} — balance: {self.leave_balance}d used: {self.leave_used}d"


class StaffLeaveUsage(models.Model):
    """One row per leave day taken by a staff member."""
    LEAVE_TYPES = [("paid", "Paid Leave"), ("absent", "Absent (Unpaid)")]
    staff      = models.ForeignKey("Staff", on_delete=models.CASCADE, related_name="leaves_taken")
    date       = models.DateField()
    leave_type = models.CharField(max_length=10, choices=LEAVE_TYPES, default="absent")
    note       = models.CharField(max_length=200, blank=True)

    class Meta:
        unique_together = ("staff", "date")
        ordering = ["-date"]

    def __str__(self):
        return f"{self.staff.staff_name} — {self.date} ({self.leave_type})"


class CompanyInterview(models.Model):
    STATUS_CHOICES = [
        ("ongoing", "Ongoing"),
        ("completed", "Completed"),
    ]

    company_name = models.CharField(max_length=200)
    role = models.CharField(max_length=200)
    interview_date = models.DateField(null=True, blank=True)

    description = models.TextField(blank=True)

    # 🔥 ADD THESE
    location = models.CharField(max_length=200, blank=True, null=True)
    salary = models.CharField(max_length=100, blank=True, null=True)

    created_by = models.ForeignKey("Staff", on_delete=models.CASCADE, related_name="interviews")

    experience = models.CharField(max_length=100, blank=True, null=True)
    skills = models.TextField(blank=True, null=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ongoing")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.company_name} - {self.role}"

class JobApplication(models.Model):

    STATUS_CHOICES = [
        ('applied', 'Applied'),
        ('shortlisted', 'Shortlisted'),
        ('rejected', 'Rejected'),
        ('selected', 'Selected'),
    ]
    course = models.CharField(max_length=80,null=True,blank=True)
    student = models.CharField(max_length=100)
    company = models.ForeignKey("CompanyInterview", on_delete=models.CASCADE)
    email = models.EmailField(null=True,blank=True)
    resume = models.CharField(max_length=500)
    phoneNumber = models.CharField(max_length=20,null=True,blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='applied')

    applied_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.student_name} → {self.company.company_name}"


class StudentProgressDashboard(models.Model):
    student = models.OneToOneField("Student", on_delete=models.CASCADE, related_name="dashboard")

    total_topics = models.IntegerField(default=0)
    finished_topics = models.IntegerField(default=0)

    ready_to_placement = models.BooleanField(default=False)
    placed = models.BooleanField(default=False)

    no_of_interviews = models.IntegerField(default=0)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.student.student_name} Dashboard"
    
    
