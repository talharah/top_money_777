import secrets
from datetime import timedelta
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

# Referral code: random, unique, phone number theke alada
REFERRAL_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'


def generate_referral_code(length=8):
    return ''.join(secrets.choice(REFERRAL_ALPHABET) for _ in range(length))

# User Profile Model
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    referral_code = models.CharField(max_length=50, unique=True, blank=True, null=True)
    referred_by = models.ForeignKey(
        'self', on_delete=models.SET_NULL, blank=True, null=True, related_name='referrals'
    )
    last_check_in = models.DateTimeField(blank=True, null=True)

    def save(self, *args, **kwargs):
                
        if not self.referral_code:
            while True:
                code = generate_referral_code()
                if not UserProfile.objects.filter(referral_code=code).exists():
                    self.referral_code = code
                    break
        super().save(*args, **kwargs)


# Deposit Model
class Deposit(models.Model):
    class Status(models.TextChoices):
        PENDING = 'Pending', 'Pending'
        APPROVED = 'Approved', 'Approved'
        REJECTED = 'Rejected', 'Rejected'

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    gateway = models.CharField(max_length=50)
    sender_number = models.CharField(max_length=15, blank=True, default='')
    trx_id = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    balance_credited = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.amount} BDT"

# Withdraw Model
class Withdraw(models.Model):
    class Status(models.TextChoices):
        PENDING = 'Pending', 'Pending'
        APPROVED = 'Approved', 'Approved'
        REJECTED = 'Rejected', 'Rejected'

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    method = models.CharField(max_length=50)
    account_number = models.CharField(max_length=20)
    account_type = models.CharField(max_length=20, default='Personal')
    fee_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    payout_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    balance_reserved = models.BooleanField(default=False)
    balance_refunded = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.amount} BDT ({self.status})"

# Investment Plans Model
class InvestmentPlan(models.Model):
    name = models.CharField(max_length=100, verbose_name="প্ল্যানের নাম (যেমন: VIP 1 / LONDON)")
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))], verbose_name="মূল্য (টাকা)")
    daily_income = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))], verbose_name="দৈনিক আয় (টাকা)")
    validity_days = models.IntegerField(validators=[MinValueValidator(1)], verbose_name="মেয়াদ (দিন)")
    image = models.ImageField(upload_to='plans/', blank=True, null=True, verbose_name="প্ল্যান ছবি")

    class Meta:
        verbose_name = "VIP প্ল্যান"
        verbose_name_plural = "VIP প্ল্যানসমূহ (Investment Plans)"

    @property
    def total_income(self):
        return self.daily_income * self.validity_days

    def __str__(self):
        return f"{self.name} - {self.price}৳"

# System Control Settings (Dynamic Website Settings)
class SystemSetting(models.Model):
    site_title = models.CharField(max_length=100, default="TOP MONEY 777", verbose_name="কোম্পানির নাম")
    welcome_bonus = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('15.00'),
        validators=[MinValueValidator(Decimal('0.00'))], verbose_name="ওয়েলকাম বোনাস (টাকা)",
    )
    min_deposit = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('350.00'),
        validators=[MinValueValidator(Decimal('0.00'))], verbose_name="সর্বনিম্ন জমা (টাকা)",
    )
    min_withdraw = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('110.00'),
        validators=[MinValueValidator(Decimal('0.00'))], verbose_name="সর্বনিম্ন উত্তোলন (টাকা)",
    )
    withdraw_fee = models.IntegerField(
        default=10, validators=[MinValueValidator(0), MaxValueValidator(100)], verbose_name="উত্তোলনের ফি (%)"
    )
    helpline_link = models.URLField(
        blank=True, default="", verbose_name="হেল্পলাইন লিংক (Telegram)"
    )
    official_group_link = models.URLField(
        blank=True, default="", verbose_name="অফিসিয়াল গ্রুপ লিংক"
    )

    class Meta:
        verbose_name = "ওয়েবসাইট সেটিংস"
        verbose_name_plural = "ওয়েবসাইট সেটিংস (Website Settings)"

    def __str__(self):
        return "ওয়েবসাইট কন্ট্রোল সেটিংস"

# Payment Method & Deposit Numbers
class PaymentMethod(models.Model):
    METHOD_CHOICES = [
        ('bkash', 'bKash'),
        ('nagad', 'Nagad'),
        ('rocket', 'Rocket'),
        ('usdt', 'USDT / Crypto'),
    ]
    name = models.CharField(max_length=50, choices=METHOD_CHOICES, verbose_name="মেথডের নাম")
    number = models.CharField(max_length=20, verbose_name="পার্সোনাল/এজেন্ট নম্বর")
    instruction = models.TextField(blank=True, null=True, verbose_name="ইউজারকে দেওয়ার নির্দেশনা")
    is_active = models.BooleanField(default=True, verbose_name="সক্রিয় আছে কিনা")

    class Meta:
        verbose_name = "পেমেন্ট মেথড ও নম্বর"
        verbose_name_plural = "পেমেন্ট মেথড ও নম্বরসমূহ (Deposit Numbers)"

    def __str__(self):
        return f"{self.get_name_display()} - {self.number}"

# Tasks Model
class Task(models.Model):
    title = models.CharField(max_length=200, verbose_name="টাস্কের নাম/শিরোনাম")
    link = models.URLField(verbose_name="কাজের লিংক (YouTube / Website / Telegram)")
    reward = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="রিওয়ার্ড/বোনাস (টাকা)",
    )
    is_active = models.BooleanField(default=True, verbose_name="চালু আছে কিনা")

    class Meta:
        verbose_name = "টাস্ক / কাজ"
        verbose_name_plural = "টাস্ক / কাজসমূহ (Tasks)"

    def __str__(self):
        return f"{self.title} - {self.reward}৳"


class UserInvestment(models.Model):
    profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='investments')
    plan = models.ForeignKey(InvestmentPlan, on_delete=models.PROTECT, related_name='purchases')
    plan_name = models.CharField(max_length=100)
    price_paid = models.DecimalField(max_digits=10, decimal_places=2)
    daily_income = models.DecimalField(max_digits=10, decimal_places=2)
    validity_days = models.PositiveIntegerField()
    purchased_at = models.DateTimeField(default=timezone.now)
    last_claimed_at = models.DateTimeField()
    days_credited = models.PositiveIntegerField(default=0)

    @property
    def is_active(self):
        return (
            self.days_credited < self.validity_days
            and timezone.now() < self.purchased_at + timedelta(days=self.validity_days)
        )

    @property
    def can_claim(self):
        return (
            self.is_active
            and timezone.now() - self.last_claimed_at >= timedelta(hours=24)
        )

    def __str__(self):
        return f"{self.profile.user.username} - {self.plan_name}"


class TaskSubmission(models.Model):
    class Status(models.TextChoices):
        PENDING = 'Pending', 'Pending'
        APPROVED = 'Approved', 'Approved'
        REJECTED = 'Rejected', 'Rejected'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='task_submissions')
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='submissions')
    proof = models.TextField(max_length=2000)
    reward_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    reward_credited = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'task'], name='unique_task_submission_per_user')
        ]

    def __str__(self):
        return f"{self.user.username} - {self.task.title} ({self.status})"


class SupportTicket(models.Model):
    class Status(models.TextChoices):
        OPEN = 'Open', 'Open'
        IN_PROGRESS = 'In progress', 'In progress'
        RESOLVED = 'Resolved', 'Resolved'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='support_tickets')
    subject = models.CharField(max_length=120)
    message = models.TextField(max_length=4000)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    admin_response = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"#{self.pk} {self.subject} - {self.user.username}"


class ReferralCommission(models.Model):
    class Level(models.IntegerChoices):
        DIRECT = 1, 'Level 1'
        SECOND = 2, 'Level 2'

    deposit = models.ForeignKey(Deposit, on_delete=models.PROTECT, related_name='commissions')
    recipient = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='commissions')
    referred_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='generated_commissions')
    level = models.PositiveSmallIntegerField(choices=Level.choices)
    rate_percent = models.DecimalField(max_digits=5, decimal_places=2)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['deposit', 'level'], name='unique_commission_per_deposit_level')
        ]

    def __str__(self):
        return f"{self.recipient.user.username} - L{self.level} - {self.amount}৳"



        # Password reset request (admin approve korle password change hoy)
class PasswordResetRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'Pending', 'Pending'
        APPROVED = 'Approved', 'Approved'
        REJECTED = 'Rejected', 'Rejected'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_reset_requests')
    new_password_hash = models.CharField(max_length=255)
    note = models.CharField(max_length=255, blank=True, default='')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Password reset request'
        verbose_name_plural = 'Password reset requests'

    def __str__(self):
        return f"{self.user.username} - {self.status}"