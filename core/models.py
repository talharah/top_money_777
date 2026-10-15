from django.db import models
from django.contrib.auth.models import User
import uuid

# User Profile Model
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=15, unique=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    referral_code = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.username

# Deposit Model
class Deposit(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    gateway = models.CharField(max_length=50) # bKash, Nagad, etc.
    trx_id = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, default='Pending') # Pending, Approved, Rejected
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.amount} BDT"

# Withdraw Model
class Withdraw(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=50)
    account_number = models.CharField(max_length=20)
    status = models.CharField(max_length=20, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.amount} BDT ({self.status})"

# Investment Plans Model
class InvestmentPlan(models.Model):
    name = models.CharField(max_length=100, verbose_name="প্ল্যানের নাম (যেমন: VIP 1 / LONDON)")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="মূল্য (টাকা)")
    daily_income = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="দৈনিক আয় (টাকা)")
    validity_days = models.IntegerField(verbose_name="মেয়াদ (দিন)")
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
    welcome_bonus = models.DecimalField(max_digits=10, decimal_places=2, default=15.00, verbose_name="ওয়েলকাম বোনাস (টাকা)")
    min_deposit = models.DecimalField(max_digits=10, decimal_places=2, default=350.00, verbose_name="সর্বনিম্ন জমা (টাকা)")
    min_withdraw = models.DecimalField(max_digits=10, decimal_places=2, default=110.00, verbose_name="সর্বনিম্ন উত্তোলন (টাকা)")
    withdraw_fee = models.IntegerField(default=10, verbose_name="উত্তোলনের ফি (%)")
    helpline_link = models.URLField(default="https://t.me/your_helpline", verbose_name="হেল্পলাইন লিংক (Telegram)")
    official_group_link = models.URLField(default="https://t.me/your_group", verbose_name="অফিসিয়াল গ্রুপ লিংক")

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
    reward = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="রিওয়ার্ড/বোনাস (টাকা)")
    is_active = models.BooleanField(default=True, verbose_name="চালু আছে কিনা")

    class Meta:
        verbose_name = "টাস্ক / কাজ"
        verbose_name_plural = "টাস্ক / কাজসমূহ (Tasks)"

    def __str__(self):
        return f"{self.title} - {self.reward}৳"