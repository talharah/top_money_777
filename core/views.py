from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.password_validation import validate_password
from django.contrib import messages
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F, Q, Sum
from django.views.decorators.http import require_POST
from .models import (
    Deposit, InvestmentPlan, PasswordResetRequest, PaymentMethod, ReferralCommission, SupportTicket,
    SystemSetting, Task, TaskSubmission, UserInvestment, UserProfile, Withdraw,
)
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.parse import urlencode

CENT = Decimal('0.01')

SUCCESS_RESET_MESSAGE = (
    'আপনার request জমা হয়েছে। অ্যাডমিন যাচাই করে approve করলে নতুন password দিয়ে লগইন করতে পারবেন।'
)

def parse_amount(value):
    try:
        amount = Decimal(value)
        quantized_amount = amount.quantize(CENT)
    except (InvalidOperation, TypeError):
        raise ValueError('সঠিক টাকার পরিমাণ লিখুন।')
    if (
        not amount.is_finite()
        or amount <= 0
        or amount > Decimal('99999999.99')
        or amount != quantized_amount
    ):
        raise ValueError('টাকার পরিমাণ ০.০১ টাকার গুণিতক হতে হবে।')
    return amount
# Login View
def login_view(request):
    if request.user.is_authenticated:
        return redirect('index')

    if request.method == 'POST':
        phone = request.POST.get('phone')
        password = request.POST.get('password')
        
        user = authenticate(request, username=phone, password=password)
        
        if user is not None:
            login(request, user)
            return redirect('index')
        else:
            return render(request, 'core/login.html', {'error': 'Invalid phone number or password!'})
            
    return render(request, 'core/login.html')

# Register View
def register_view(request):
    if request.user.is_authenticated:
        return redirect('index')

    # URL theke refer-er code songroho kora (jemon: /register/?ref=username)
    ref_code = request.GET.get('ref')

    if request.method == 'POST':
        full_name = request.POST.get('fullname', '').strip()
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password', '')
        ref_code = (request.POST.get('referral_code') or ref_code or '').strip()
        
        if not full_name or not phone or len(phone) > 15:
            return render(request, 'core/register.html', {
                'error': 'নাম দিতে হবে এবং ফোন নম্বর ১৫ অক্ষরের মধ্যে হতে হবে।',
                'ref_code': ref_code,
            })
        if password != request.POST.get('confirm_password'):
            return render(request, 'core/register.html', {
                'error': 'দুটি password মেলেনি।',
                'ref_code': ref_code,
            })
        if User.objects.filter(username=phone).exists():
            return render(request, 'core/register.html', {
                'error': 'এই ফোন নম্বর দিয়ে ইতিমধ্যে অ্যাকাউন্ট খোলা হয়েছে।',
                'ref_code': ref_code,
            })

        candidate = User(username=phone, first_name=full_name)
        try:
            validate_password(password, user=candidate)
        except ValidationError as error:
            return render(request, 'core/register.html', {
                'error': ' '.join(error.messages),
                'ref_code': ref_code,
            })
        
        # User toiri kora
        user = User.objects.create_user(username=phone, password=password, first_name=full_name)
        
        # UserProfile toiri kora ebong ke refer koreche ta track kora (jodi apnar model-e referred_by ba similar kono field thake)
        setting, _ = SystemSetting.objects.get_or_create(pk=1)
        profile, _ = UserProfile.objects.get_or_create(
            user=user,
            defaults={'phone_number': phone, 'balance': setting.welcome_bonus},
        )
        
        referrer_profile = UserProfile.objects.filter(referral_code__iexact=ref_code).exclude(user=user).first()
        if referrer_profile:
            profile.referred_by = referrer_profile
            profile.save(update_fields=['referred_by'])
        
        return redirect('login')
        
    return render(request, 'core/register.html', {'ref_code': ref_code})

def forgot_password_view(request):
    if request.user.is_authenticated:
        return redirect('change_password')

    setting, _ = SystemSetting.objects.get_or_create(pk=1)

    if request.method == 'POST':
        phone = request.POST.get('phone', '').strip()
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')
        note = request.POST.get('note', '').strip()[:255]

        if not phone or not new_password:
            messages.error(request, 'ফোন নম্বর এবং নতুন password দিন।')
        elif new_password != confirm_password:
            messages.error(request, 'দুটি password মেলেনি।')
        else:
            user = User.objects.filter(username=phone).first()
            if user is None:
                messages.success(request, SUCCESS_RESET_MESSAGE)
                return redirect('forgot_password')
            try:
                validate_password(new_password, user=user)
            except ValidationError as error:
                messages.error(request, ' '.join(error.messages))
            else:
                with transaction.atomic():
                    pending = PasswordResetRequest.objects.select_for_update().filter(
                        user=user, status=PasswordResetRequest.Status.PENDING
                    ).first()
                    if pending:
                        pending.new_password_hash = make_password(new_password)
                        pending.note = note
                        pending.save(update_fields=['new_password_hash', 'note', 'updated_at'])
                    else:
                        PasswordResetRequest.objects.create(
                            user=user,
                            new_password_hash=make_password(new_password),
                            note=note,
                        )
                messages.success(request, SUCCESS_RESET_MESSAGE)
                return redirect('forgot_password')
    return render(request, 'core/forgot_pass.html', {'setting': setting})

# Logout View
@login_required(login_url='login')
def logout_view(request):
    logout(request)
    return redirect('login')

# Dashboard / Index View
@login_required(login_url='login')
def index_view(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    setting, _ = SystemSetting.objects.get_or_create(pk=1)
    investments = list(
        UserInvestment.objects.filter(profile=profile).select_related('plan').order_by('-purchased_at')
    )
    active_investments = [investment for investment in investments if investment.is_active]
    recent_deposits = Deposit.objects.filter(user=request.user).order_by('-created_at')[:5]
    recent_withdrawals = Withdraw.objects.filter(user=request.user).order_by('-created_at')[:5]

    context = {
        'profile': profile,
        'setting': setting,
        'investments': active_investments,
        'is_vip_member': bool(active_investments),
        'active_plan_names': ', '.join(dict.fromkeys(item.plan_name for item in active_investments)) or 'None',
        'daily_reward_available': (
            profile.last_check_in is None
            or timezone.now() - profile.last_check_in >= timedelta(hours=24)
        ),
        'total_invested': sum((item.price_paid for item in investments), Decimal('0.00')),
        'total_earnings': sum(
            (item.daily_income * item.days_credited for item in investments), Decimal('0.00')
        ),
        'recent_deposits': recent_deposits,
        'recent_withdrawals': recent_withdrawals,
        'recent_activity': sorted(
            [
                {
                    'title': f'Deposit ({deposit.gateway})',
                    'date': deposit.created_at,
                    'amount': deposit.amount,
                    'status': deposit.status,
                    'kind': (
                        'credit' if deposit.status == Deposit.Status.APPROVED
                        else 'rejected' if deposit.status == Deposit.Status.REJECTED
                        else 'pending'
                    ),
                }
                for deposit in recent_deposits
            ] + [
                {
                    'title': f'Withdraw ({withdrawal.method})',
                    'date': withdrawal.created_at,
                    'amount': withdrawal.amount,
                    'status': (
                        f'{withdrawal.status} - refunded'
                        if withdrawal.balance_refunded else withdrawal.status
                    ),
                    'kind': (
                        'debit' if withdrawal.status == Withdraw.Status.APPROVED
                        else 'credit' if withdrawal.balance_refunded
                        else 'rejected' if withdrawal.status == Withdraw.Status.REJECTED
                        else 'pending'
                    ),
                }
                for withdrawal in recent_withdrawals
            ],
            key=lambda item: item['date'],
            reverse=True,
        )[:5],
        'pending_task_count': TaskSubmission.objects.filter(
            user=request.user, status=TaskSubmission.Status.PENDING
        ).count(),
    }
    return render(request, 'core/index.html', context)

@login_required(login_url='login')
def tasks_view(request):
    tasks = list(Task.objects.filter(is_active=True).order_by('id'))
    submissions = {
        submission.task_id: submission
        for submission in TaskSubmission.objects.filter(user=request.user, task__in=tasks)
    }
    for task in tasks:
        task.user_submission = submissions.get(task.id)
    return render(request, 'core/tasks.html', {'tasks': tasks})

@login_required(login_url='login')
def plans_view(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    plans = InvestmentPlan.objects.all()
    
    if request.method == 'POST':
        plan_id = request.POST.get('plan_id')
        try:
            plan = InvestmentPlan.objects.get(id=plan_id)
            if plan.validity_days < 1 or plan.daily_income <= 0 or plan.price <= 0:
                messages.error(request, 'এই প্ল্যানটি এখন কেনা যাচ্ছে না।')
                return redirect('plans')

            with transaction.atomic():
                updated = UserProfile.objects.filter(
                    pk=profile.pk, balance__gte=plan.price
                ).update(balance=F('balance') - plan.price)
                if not updated:
                    messages.error(request, f'আপনার একাউন্টে পর্যাপ্ত ব্যালেন্স নেই! {plan.name} কিনতে ৳{plan.price} প্রয়োজন।')
                else:
                    profile.refresh_from_db(fields=['balance'])
                    now = timezone.now()
                    UserInvestment.objects.create(
                        profile=profile,
                        plan=plan,
                        plan_name=plan.name,
                        price_paid=plan.price,
                        daily_income=plan.daily_income,
                        validity_days=plan.validity_days,
                        purchased_at=now,
                        last_claimed_at=now,
                    )
                    messages.success(request, f'অভিনন্দন! আপনি সফলভাবে {plan.name} প্ল্যানটি কিনেছেন। প্রথম দৈনিক আয় ২৪ ঘণ্টা পর দাবি করতে পারবেন।')
        except (InvestmentPlan.DoesNotExist, ValueError, ValidationError):
            messages.error(request, 'আবেদনকৃত প্ল্যানটি খুঁজে পাওয়া যায়নি।')
            
        return redirect('plans')

    context = {
        'plans': plans,
        'profile': profile,
        'investments': UserInvestment.objects.filter(profile=profile).order_by('-purchased_at'),
    }
    return render(request, 'core/plans.html', context)

@login_required(login_url='login')
def profile_view(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    investments = UserInvestment.objects.filter(profile=profile)
    is_vip_member = any(investment.is_active for investment in investments)
    return render(request, 'core/profile.html', {
        'profile': profile,
        'is_vip_member': is_vip_member,
    })

@login_required(login_url='login')
def withdraw_view(request):
    setting, _ = SystemSetting.objects.get_or_create(pk=1)
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        try:
            amount = parse_amount(request.POST.get('amount'))
        except ValueError as error:
            messages.error(request, str(error))
            return redirect('withdraw')

        method = request.POST.get('gateway', request.POST.get('method', '')).strip()
        account_number = request.POST.get('receiver_number', request.POST.get('account_number', '')).strip()
        account_type = request.POST.get('account_type', 'Personal').strip()
        if method not in {'bKash', 'Nagad', 'Rocket'}:
            messages.error(request, 'বৈধ withdrawal method নির্বাচন করুন।')
            return redirect('withdraw')
        if not account_number or len(account_number) > 20:
            messages.error(request, 'সঠিক receiver account number লিখুন।')
            return redirect('withdraw')
        if account_type not in {'Personal', 'Agent'}:
            messages.error(request, 'বৈধ account type নির্বাচন করুন।')
            return redirect('withdraw')
        if setting.withdraw_fee < 0 or setting.withdraw_fee > 100:
            messages.error(request, 'উত্তোলনের ফি সেটিংস সঠিক নয়। অ্যাডমিনের সঙ্গে যোগাযোগ করুন।')
            return redirect('withdraw')
        if amount < setting.min_withdraw:
            messages.error(request, f'সর্বনিম্ন উত্তোলনের পরিমাণ ৳{setting.min_withdraw}।')
            return redirect('withdraw')

        fee_amount = (amount * Decimal(setting.withdraw_fee) / Decimal('100')).quantize(
            CENT, rounding=ROUND_HALF_UP
        )
        try:
            with transaction.atomic():
                updated = UserProfile.objects.filter(
                    pk=profile.pk, balance__gte=amount
                ).update(balance=F('balance') - amount)
                if updated:
                    Withdraw.objects.create(
                        user=request.user,
                        amount=amount,
                        method=method,
                        account_number=account_number,
                        account_type=account_type,
                        fee_amount=fee_amount,
                        payout_amount=amount - fee_amount,
                        balance_reserved=True,
                    )
        except (IntegrityError, ValidationError):
            messages.error(request, 'উইথড্র রিকোয়েস্ট জমা হয়নি। আবার চেষ্টা করুন।')
            return redirect('withdraw')
        if not updated:
            messages.error(request, 'আপনার ব্যালেন্সে পর্যাপ্ত টাকা নেই।')
            return redirect('withdraw')

        messages.success(
            request,
            f'উইথড্র রিকোয়েস্ট জমা হয়েছে। ৳{amount} ব্যালেন্স থেকে সংরক্ষিত; ফি ৳{fee_amount}, প্রাপ্য ৳{amount - fee_amount}।',
        )
        return redirect('index')

    return render(request, 'core/withdraw.html', {'setting': setting, 'profile': profile})

@login_required(login_url='login')
def deposit_view(request):
    methods = PaymentMethod.objects.filter(is_active=True)
    setting, _ = SystemSetting.objects.get_or_create(pk=1)
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        try:
            amount = parse_amount(request.POST.get('amount'))
        except ValueError as error:
            messages.error(request, str(error))
            return redirect('deposit')

        gateway = request.POST.get('gateway', '').strip()
        sender_number = request.POST.get('sender_number', '').strip()
        trx_id = request.POST.get('trx_id', '').strip().upper()
        if not PaymentMethod.objects.filter(name=gateway, is_active=True).exists():
            messages.error(request, 'বৈধ ও সক্রিয় payment method নির্বাচন করুন।')
            return redirect('deposit')
        if amount < setting.min_deposit:
            messages.error(request, f'সর্বনিম্ন ডিপোজিটের পরিমাণ ৳{setting.min_deposit}।')
            return redirect('deposit')
        if not sender_number or len(sender_number) > 15:
            messages.error(request, 'সঠিক sender mobile number লিখুন।')
            return redirect('deposit')
        if not trx_id or len(trx_id) > 100:
            messages.error(request, 'সঠিক transaction ID লিখুন।')
            return redirect('deposit')
        if Deposit.objects.filter(trx_id=trx_id).exists():
            messages.error(request, 'এই transaction ID আগে ব্যবহার করা হয়েছে।')
            return redirect('deposit')
        try:
            Deposit.objects.create(
                user=request.user,
                amount=amount,
                gateway=gateway,
                sender_number=sender_number,
                trx_id=trx_id,
            )
        except IntegrityError:
            messages.error(request, 'এই transaction ID আগে ব্যবহার করা হয়েছে।')
            return redirect('deposit')
        messages.success(request, 'ডিপোজিট রিকোয়েস্ট জমা হয়েছে। অ্যাডমিন যাচাই করে অনুমোদন করলে ব্যালেন্স যোগ হবে।')
        return redirect('index')

    return render(request, 'core/deposit.html', {
        'methods': methods,
        'setting': setting,
        'profile': profile,
    })

@login_required(login_url='login')
def refer_view(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    referral_link = (
        f"{request.build_absolute_uri('/register/')}?{urlencode({'ref': profile.referral_code})}"
    )
    commissions = ReferralCommission.objects.filter(recipient=profile)
    
    context = {
        'profile': profile,
        'referral_link': referral_link,
        'referral_count': profile.referrals.count(),
        'referral_earnings': commissions.aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
        'level_one_rate': 10,
        'level_two_rate': 3,
    }
    return render(request, 'core/refer.html', context)

@login_required(login_url='login')
def support_view(request):
    setting, _ = SystemSetting.objects.get_or_create(pk=1)
    if request.method == 'POST':
        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()
        valid_subjects = {
            'Deposit Issue', 'Withdraw Issue', 'Task / Reward Issue',
            'Account Issue', 'Other Query',
        }
        if subject not in valid_subjects or not message or len(message) > 4000:
            messages.error(request, 'বিষয় নির্বাচন করে ৪০০০ অক্ষরের মধ্যে সমস্যার বিবরণ লিখুন।')
        else:
            SupportTicket.objects.create(user=request.user, subject=subject, message=message)
            messages.success(request, 'আপনার support ticket জমা হয়েছে। অ্যাডমিন প্যানেল থেকে এটি দেখা যাবে।')
            return redirect('support')
    return render(request, 'core/support.html', {
        'setting': setting,
        'tickets': SupportTicket.objects.filter(user=request.user).order_by('-created_at')[:10],
    })

@login_required(login_url='login')
def personal_info_view(request):
    full_name = request.user.first_name
    email = request.user.email
    if request.method == 'POST':
        user = request.user
        full_name = request.POST.get('full_name', '').strip()
        email = request.POST.get('email', '').strip()
        if not full_name or len(full_name) > 150:
            messages.error(request, 'নাম লিখুন (সর্বোচ্চ ১৫০ অক্ষর)।')
        else:
            try:
                if email:
                    validate_email(email)
            except ValidationError:
                messages.error(request, 'সঠিক ইমেইল ঠিকানা লিখুন।')
            else:
                user.first_name = full_name
                user.email = email
                user.save(update_fields=['first_name', 'email'])
                messages.success(request, 'আপনার তথ্য আপডেট হয়েছে।')
                return redirect('personal_info')
    return render(request, 'core/personal_info.html', {
        'full_name': full_name,
        'email': email,
    })

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



@login_required(login_url='login')
def history_view(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    history_items = []
    for deposit in Deposit.objects.filter(user=request.user):
        history_items.append({
            'title': f'Deposit ({deposit.gateway})',
            'date': deposit.created_at,
            'amount': deposit.amount,
            'status': deposit.status,
            'kind': 'credit' if deposit.status == Deposit.Status.APPROVED else 'pending',
        })
    for withdrawal in Withdraw.objects.filter(user=request.user):
        history_items.append({
            'title': (
                f'Withdraw refund ({withdrawal.method})'
                if withdrawal.balance_refunded else f'Withdraw ({withdrawal.method})'
            ),
            'date': withdrawal.created_at,
            'amount': withdrawal.amount,
            'status': (
                f'{withdrawal.status} - refunded'
                if withdrawal.balance_refunded else withdrawal.status
            ),
            'kind': (
                'debit' if withdrawal.status == Withdraw.Status.APPROVED
                else 'credit' if withdrawal.balance_refunded
                else 'pending'
            ),
        })
    if profile.last_check_in:
        history_items.append({
            'title': 'Daily check-in reward',
            'date': profile.last_check_in,
            'amount': Decimal('5.00'),
            'status': 'Credited',
            'kind': 'credit',
        })
    for commission in ReferralCommission.objects.filter(recipient=profile):
        history_items.append({
            'title': f'Level {commission.level} referral commission',
            'date': commission.created_at,
            'amount': commission.amount,
            'status': 'Credited',
            'kind': 'credit',
        })
    for submission in TaskSubmission.objects.filter(
        user=request.user, status=TaskSubmission.Status.APPROVED, reward_credited=True
    ).select_related('task'):
        history_items.append({
            'title': f'Task reward ({submission.task.title})',
            'date': submission.updated_at,
            'amount': submission.reward_amount,
            'status': 'Credited',
            'kind': 'credit',
        })
    for investment in UserInvestment.objects.filter(profile=profile).exclude(days_credited=0):
        history_items.append({
            'title': f'VIP earnings ({investment.plan_name})',
            'date': investment.last_claimed_at,
            'amount': investment.daily_income * investment.days_credited,
            'status': f'{investment.days_credited} daily claim(s)',
            'kind': 'credit',
        })
    history_items.sort(key=lambda item: item['date'], reverse=True)
    return render(request, 'core/history.html', {'history_list': history_items})



@login_required(login_url='login')
@require_POST
def submit_task_view(request, task_id):
    task = Task.objects.filter(pk=task_id, is_active=True).first()
    if task is None:
        messages.error(request, 'এই task আর সক্রিয় নেই।')
        return redirect('tasks')

    proof = request.POST.get('proof', '').strip()
    if not proof or len(proof) > 2000:
        messages.error(request, 'Task সম্পন্ন করার প্রমাণ বা বিবরণ ২০০০ অক্ষরের মধ্যে লিখুন।')
        return redirect('tasks')

    submission, created = TaskSubmission.objects.get_or_create(
        user=request.user,
        task=task,
        defaults={'proof': proof, 'reward_amount': task.reward},
    )
    if created:
        messages.success(request, 'আপনার task proof জমা হয়েছে। অ্যাডমিন অনুমোদন করলে reward ব্যালেন্সে যোগ হবে।')
    elif submission.status == TaskSubmission.Status.REJECTED:
        submission.proof = proof
        submission.status = TaskSubmission.Status.PENDING
        submission.save(update_fields=['proof', 'status', 'updated_at'])
        messages.success(request, 'Task proof আবার জমা হয়েছে। অ্যাডমিন যাচাই করবেন।')
    elif submission.status == TaskSubmission.Status.PENDING:
        messages.info(request, 'এই task-এর proof ইতিমধ্যে যাচাইয়ের অপেক্ষায় আছে।')
    else:
        messages.info(request, 'এই task-এর reward ইতিমধ্যে অনুমোদিত হয়েছে।')
    return redirect('tasks')


@login_required(login_url='login')
@require_POST
def claim_plan_income_view(request, investment_id):
    with transaction.atomic():
        investment = UserInvestment.objects.select_for_update().filter(
            pk=investment_id, profile__user=request.user
        ).first()
        if investment is None:
            messages.error(request, 'VIP investment পাওয়া যায়নি।')
            return redirect('index')
        if not investment.can_claim:
            messages.error(request, 'এই investment-এর দৈনিক আয় এখন দাবি করা যাবে না। ২৪ ঘণ্টা পর আবার চেষ্টা করুন।')
            return redirect('index')

        now = timezone.now()
        claimed = UserInvestment.objects.filter(
            pk=investment.pk,
            days_credited__lt=investment.validity_days,
            last_claimed_at__lte=now - timedelta(hours=24),
        ).update(days_credited=F('days_credited') + 1, last_claimed_at=now)
        if not claimed:
            messages.error(request, 'এই investment-এর দৈনিক আয় ইতিমধ্যে দাবি করা হয়েছে।')
            return redirect('index')
        UserProfile.objects.filter(pk=investment.profile_id).update(
            balance=F('balance') + investment.daily_income
        )

    messages.success(request, f'{investment.plan_name} থেকে ৳{investment.daily_income} দৈনিক আয় মেইন ব্যালেন্সে যোগ হয়েছে।')
    return redirect('index')


@login_required(login_url='login')
@require_POST
def daily_checkin_view(request):
    with transaction.atomic():
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        now = timezone.now()
        reward_amount = Decimal('5.00')
        claimed = UserProfile.objects.filter(pk=profile.pk).filter(
            Q(last_check_in__isnull=True)
            | Q(last_check_in__lte=now - timedelta(hours=24))
        ).update(balance=F('balance') + reward_amount, last_check_in=now)
        already_claimed = not claimed

    if already_claimed:
        messages.error(request, 'আপনি ইতিমধ্যে গত ২৪ ঘণ্টার মধ্যে ডেইলি রিওয়ার্ড গ্রহণ করেছেন। আবার ২৪ ঘণ্টা পর চেষ্টা করুন!')
    else:
        messages.success(request, f'অভিনন্দন! সফলভাবে ৳{reward_amount} ডেইলি রিওয়ার্ড মেইন ব্যালেন্সে যোগ হয়েছে।')
        
    return redirect('index')
