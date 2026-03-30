from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('login/',          views.staff_login,    name='staff_login'),
    path('logout/',         views.staff_logout,   name='staff_logout'),
    path('register_staff/', views.register_staff, name='register_staff'),

    # Staff — batch dashboard
    path('get_batches/', views.getBatches, name='get_batches'),

    # Staff — students
    path('students/<int:batch_id>/',                          views.student_list,   name='student_list'),
    path('student/<int:student_id>/<int:batch_id>',           views.student_detail, name='student_detail'),
    path('student/<int:student_id>/<int:batch_id>/progress/', views.add_progress,   name='add_progress'),

    # Staff — attendance
    path('attendance/<int:batch_id>', views.mark_student_attendance, name='student_attendance'),

    # Staff — batch CRUD
    path('add_batch/',                   views.add_batch,    name='add_batch'),
    path('edit_batch/<int:batch_id>/',   views.edit_batch,   name='edit_batch'),
    path('delete_batch/<int:batch_id>/', views.delete_batch, name='delete_batch'),

    # Staff — add student modal
    path('staff/add-student/', views.staff_add_student, name='staff_add_student'),

    # Staff — course self-learning API
    path('staff/course-topics/<int:course_id>/', views.staff_course_topics, name='staff_course_topics'),
    path('staff/toggle-topic/<int:topic_id>/',   views.staff_toggle_topic,  name='staff_toggle_topic'),

    # Staff — own attendance (read-only calendar)
    path('my-attendance/', views.staff_own_attendance, name='staff_own_attendance'),

    # Admin dashboard
    path('admin-dashboard/',             views.admin_dashboard,   name='admin_dashboard'),
    path('admin-dashboard/get-staff/',   views.admin_get_staff,   name='admin_get_staff'),
    path('admin-dashboard/get-batches/', views.admin_get_batches, name='admin_get_batches'),
    path('admin-dashboard/add-student/', views.admin_add_student, name='admin_add_student'),
    path('admin-dashboard/add-course/',  views.admin_add_course,  name='admin_add_course'),
    path('admin-dashboard/add-topic/',   views.admin_add_topic,   name='admin_add_topic'),
    path('admin-dashboard/add-staff/',   views.admin_add_staff,   name='admin_add_staff'),
    path('admin-dashboard/enroll-staff/', views.admin_enroll_staff, name='admin_enroll_staff'),

    # Admin — attendance calendars
    path('admin-dashboard/staff-attendance/<int:staff_id>/',
         views.admin_staff_attendance_calendar,
         name='staff_attendance_calendar'),
    path('admin-dashboard/student-attendance/<int:student_id>/',
         views.admin_student_attendance_calendar,
         name='admin_student_attendance_calendar'),

    # Admin — student progress
    path('admin-dashboard/students-overview/',
         views.admin_students_overview,
         name='admin_students_overview'),
    path('admin-dashboard/students-overview/<int:student_id>/',
         views.admin_student_progress_detail,
         name='admin_student_progress_detail'),

     #Attendance Toggle
     path('toggle-wifi/<int:attendance_id>/', views.toggle_wifi, name='toggle_wifi'),

     path('placement-dashboard/', views.placement_dashboard, name='placement_dashboard'),
     path('add-company/', views.add_company, name='add_company'),
     path('complete/<int:id>/', views.complete_interview, name='complete_interview'),
     
    # Home — must be last
    path('', views.home, name='home'),
]