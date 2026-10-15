from django.urls import path
from django.views.generic import RedirectView  # এই লাইনটি মিসিং ছিল!
from . import views

urlpatterns = [
    path('', views.index_view, name='index'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('tasks/', views.tasks_view, name='tasks'),
    path('plans/', views.plans_view, name='plans'),
    path('profile/', views.profile_view, name='profile'),
    path('withdraw/', views.withdraw_view, name='withdraw'),
    path('deposit/', views.deposit_view, name='deposit'),
    path('refer/', views.refer_view, name='refer'),
    path('support/', views.support_view, name='support'),
    path('logout/', views.logout_view, name='logout'),
    # ক্যাশ বা ভুল লিংকের রিডাইরেক্ট রুলস
    path('login/register.html', RedirectView.as_view(pattern_name='register', permanent=False)),
    path('register/login.html', RedirectView.as_view(pattern_name='login', permanent=False)),
    path('login/index.html', RedirectView.as_view(pattern_name='index', permanent=False)),
    path('profile/edit/', views.personal_info_view, name='personal_info'),
    path('profile/password/', views.change_password_view, name='change_password'),
     path('history/', views.history_view, name='history'),
]