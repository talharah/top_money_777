from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.db import transaction
from .models import UserProfile, Deposit, Withdraw, InvestmentPlan, SystemSetting, Task, PaymentMethod

# Login View
def login_view(request):
    if request.user.is_authenticated:
        return redirect('index')

    if request.method == 'POST':
        phone = request.POST.get('phone')
        password = request.POST.get('password')
        
        print(f"--> TRYING LOGIN WITH PHONE: {phone}")
        
        user = authenticate(request, username=phone, password=password)
        
        if user is not None:
            login(request, user)
            print(f"--> LOGIN SUCCESSFUL FOR USER: {user.username}")
            return redirect('index')
        else:
            print("--> AUTHENTICATION FAILED! Wrong Phone or Password.")
            return render(request, 'core/login.html', {'error': 'Invalid phone number or password!'})
            
    return render(request, 'core/login.html')

# Register View
def register_view(request):
    if request.user.is_authenticated:
        return redirect('index')

    # URL থেকে রেফারের কোড সংগ্রহ করা (যেমন: /register/?ref=017XXXXXXXX)
    ref_code = request.GET.get('ref')

    if request.method == 'POST':
        full_name = request.POST.get('fullname')
        phone = request.POST.get('phone')
        password = request.POST.get('password')
        
        if User.objects.filter(username=phone).exists():
            return render(request, 'core/register.html', {'error': 'This phone number is already registered!'})
        
        user = User.objects.create_user(username=phone, password=password, first_name=full_name)
        
        # কে রেফার করেছে তা এখানে প্রসেস করতে পারেন চাইলে কোনো ফিল্ডে সেভ করে
        UserProfile.objects.get_or_create(user=user, phone_number=phone)
        
        return redirect('login')
        
    return render(request, 'core/register.html')

# Logout View
@login_required(login_url='login')
def logout_view(request):
    logout(request)
    return redirect('login')

# Dashboard / Index View
@login_required(login_url='login')
def index_view(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    # Fetch Website Settings for dynamic popup & data
    setting = SystemSetting.objects.first()
    if not setting:
        setting = SystemSetting.objects.create()

    context = {
        'profile': profile,
        'setting': setting,
    }
    return render(request, 'core/index.html', context)

@login_required(login_url='login')
def tasks_view(request):
    tasks = Task.objects.filter(is_active=True)
    return render(request, 'core/tasks.html', {'tasks': tasks})

@login_required(login_url='login')
def plans_view(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    plans = InvestmentPlan.objects.all()
    
    if request.method == 'POST':
        plan_id = request.POST.get('plan_id')
        try:
            plan = InvestmentPlan.objects.get(id=plan_id)
            
            # ব্যালেন্স চেক এবং নিরাপদ ট্রানজেকশন লজিক
            if profile.balance >= plan.price:
                with transaction.atomic():
                    profile.balance -= plan.price
                    profile.save()
                    messages.success(request, f'অভিনন্দন! আপনি সফলভাবে {plan.name} প্ল্যানটি কিনেছেন।')
            else:
                messages.error(request, f'আপনার একাউন্টে পর্যাপ্ত ব্যালেন্স নেই! {plan.name} কিনতে ৳{plan.price} প্রয়োজন।')
                
        except InvestmentPlan.DoesNotExist:
            messages.error(request, 'আবেদনকৃত প্ল্যানটি খুঁজে পাওয়া যায়নি।')
            
        return redirect('plans')

    context = {
        'plans': plans,
        'profile': profile,
    }
    return render(request, 'core/plans.html', context)

@login_required(login_url='login')
def profile_view(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    return render(request, 'core/profile.html', {'profile': profile})

@login_required(login_url='login')
def withdraw_view(request):
    setting = SystemSetting.objects.first()
    if request.method == 'POST':
        amount = request.POST.get('amount')
        method = request.POST.get('method')
        account_number = request.POST.get('account_number')
        
        Withdraw.objects.create(
            user=request.user,
            amount=amount,
            method=method,
            account_number=account_number,
            status='Pending'
        )
        return redirect('index')
        
    return render(request, 'core/withdraw.html', {'setting': setting})

@login_required(login_url='login')
def deposit_view(request):
    methods = PaymentMethod.objects.filter(is_active=True)
    setting = SystemSetting.objects.first()
    
    if request.method == 'POST':
        amount = request.POST.get('amount')
        gateway = request.POST.get('gateway')
        trx_id = request.POST.get('trx_id')
        
        Deposit.objects.create(
            user=request.user,
            amount=amount,
            gateway=gateway,
            trx_id=trx_id,
            status='Pending'
        )
        return redirect('index')
        
    return render(request, 'core/deposit.html', {'methods': methods, 'setting': setting})

@login_required(login_url='login')
def refer_view(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    # ডোমেইনসহ সম্পূর্ণ রেফার লিংক তৈরি (যেমন: http://127.0.0.1:8000/register/?ref=017XXXXXXXX)
    domain = request.get_host()
    referral_link = f"http://{domain}/register/?ref={profile.referral_code}"
    
    context = {
        'profile': profile,
        'referral_link': referral_link,
    }
    return render(request, 'core/refer.html', context)

@login_required(login_url='login')
def support_view(request):
    setting = SystemSetting.objects.first()
    return render(request, 'core/support.html', {'setting': setting})

@login_required(login_url='login')
def personal_info_view(request):
    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('full_name', '')
        user.save()
        return redirect('profile')
    return render(request, 'core/personal_info.html')

@login_required(login_url='login')
def change_password_view(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            return redirect('profile')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'core/change_password.html', {'form': form})



@login_required
def history_view(request):
    # আপাতত খালি লিস্ট পাস করা হলো, যাতে এরর না আসে। পরবর্তীতে আপনার মডেল অনুযায়ী ডাটা যুক্ত করতে পারবেন।
    history_list = [] 
    return render(request, 'core/history.html', {'history_list': history_list})