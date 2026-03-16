# myapp/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from .models import Student
from django.contrib.auth.signals import user_logged_in
from .models import Staff, Attendance
from django.utils import timezone
from django.conf import settings
import socket

def get_local_ip():
    """Get the device's current LAN/WiFi IP"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn’t need to succeed; just binds to a network interface
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception as e:
        print(f"❌ Failed to fetch local IP: {e}")
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

@receiver(post_save, sender=Student)#automatically calls when a new student is created
def notify_staff_on_new_student(sender, instance, created, **kwargs):
    if created:  # only when new student is added
        staff = instance.staff
        subject = f"New Student Assigned: {instance.student_name}"
        

        message = f"""
Dear {staff.staff_name},

A new student has been assigned to you.

Student Details:
----------------
Name       : {instance.student_name}
Email      : {instance.student_email}
Contact    : {instance.student_contact}
Course     : {instance.course.course_name}
Batch      : {"Morning" if instance.batch else "Afternoon"}
Mode       : {"Online" if instance.mode else "Offline"}
Join Date  : {instance.join_date}
End Date   : {instance.end_date if instance.end_date else "-"}

Please check your portal for further details.

Regards,  
Admin Team
"""

        # pick the staff email from Staff model first, fallback to User
        recipient = staff.staff_email or staff.user.email

        if recipient:
            try:
                send_mail(
                    subject,
                    message,
                    None,  # DEFAULT_FROM_EMAIL
                    [recipient],
                    fail_silently=False,
                )
                print(f"✅ Notification email sent to {recipient} for new student {instance.student_name}.")
            except Exception as e:
                print("email failed : ",e)
        else:
            print(f"⚠️ No email found for staff {staff.staff_name}.")


@receiver(user_logged_in)
def mark_attendance(sender, request, user, **kwargs):
    try:
        staff = Staff.objects.get(user=user)
    except Staff.DoesNotExist:
        return  # only apply to staff

    today = timezone.now().date()
    ip = get_client_ip(request)
    wifi_verified = ip in getattr(settings, "ALLOWED_WIFI_IPS", [])

    # Case 1: If verified attendance already exists → do nothing
    if Attendance.objects.filter(staff=staff, date=today, wifi_verified=True).exists():
        print(f"⚠️ Attendance already marked with WiFi verified for {staff.staff_name} on {today}")
        return

    # Case 2: If logging in with WiFi verified → create new record
    if wifi_verified:
        Attendance.objects.create(staff=staff, date=today, wifi_verified=True)
        print(f"✅ Attendance (WiFi Verified) marked for {staff.staff_name} on {today} {ip}")
    else:
        # Case 3: Allow multiple unverified? → Only one unverified per day
        if not Attendance.objects.filter(staff=staff, date=today, wifi_verified=False).exists():
            Attendance.objects.create(staff=staff, date=today, wifi_verified=False)
            print(f"✅ Attendance (Unverified WiFi) marked for {staff.staff_name} on {today} {ip}")
        else:
            print(f"⚠️ Attendance (Unverified) already exists for {staff.staff_name} on {today} {ip}")
            
    print("DEBUG IP:", repr(ip))
    print("DEBUG SETTINGS ALLOWED:", repr(getattr(settings, "ALLOWED_WIFI_IPS", [])))


    print(f"   🌐 Final IP used: {ip}")
    print(f"   📶 WiFi Verified: {wifi_verified}")

def get_client_ip(request):
    """Get client IP address from request"""
    print("META HEADERS:", request.META)
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")

    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
        print(f"🔎 IP from X-Forwarded-For: {ip}")
        return ip

    x_real_ip = request.META.get("HTTP_X_REAL_IP")
    if x_real_ip:
        print(f"🔎 IP from X-Real-IP: {x_real_ip}")
        return x_real_ip

    ip = request.META.get("REMOTE_ADDR")
    print(f"🔎 IP from REMOTE_ADDR: {ip}")

    return ip

