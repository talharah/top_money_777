from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),  # আপনার core অ্যাপের urls এখানে যুক্ত থাকবে
]