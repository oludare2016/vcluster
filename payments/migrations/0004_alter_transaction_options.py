# Generated by Django 5.0.8 on 2024-08-18 15:54

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0003_transaction"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="transaction",
            options={
                "verbose_name": "Transaction",
                "verbose_name_plural": "Transactions",
            },
        ),
    ]
