# Generated by Django 5.0.7 on 2024-08-03 05:56

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("referrals", "0002_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="staff",
            name="first_name",
        ),
        migrations.RemoveField(
            model_name="staff",
            name="last_name",
        ),
        migrations.RemoveField(
            model_name="staff",
            name="phone_number",
        ),
    ]
