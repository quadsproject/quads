from wtforms import validators, SelectMultipleField, StringField, BooleanField, SelectField, IntegerField
from flask_wtf import FlaskForm
from quads.config import Config


class ModelSearchForm(FlaskForm):
    models_list = Config.models.split(",")
    models_choices = []
    for model in models_list:
        models_choices.append((model, model))
    model = SelectMultipleField("Models:", choices=models_choices)
    date_range = StringField("Date Range:", validators=[validators.DataRequired()])
    has_gpu = BooleanField("Has GPU")
    disk_types = SelectMultipleField("Disk Types:", choices=[])
    disk_size_operator = SelectField(
        "Disk Size Operator:",
        choices=[("", ""), ("eq", "=="), ("ne", "!="), ("gt", ">"), ("lt", "<"), ("gte", ">="), ("lte", "<=")],
    )
    disk_size_value = IntegerField("Disk Size (GB):", validators=[validators.Optional()])
    disk_count_operator = SelectField(
        "Disk Count Operator:",
        choices=[("", ""), ("eq", "=="), ("ne", "!="), ("gt", ">"), ("lt", "<"), ("gte", ">="), ("lte", "<=")],
    )
    disk_count_value = IntegerField("Disk Count:", validators=[validators.Optional()])
    nic_vendors = getattr(Config, "nic_vendors", [])
    nic_vendors_choices = [(vendor, vendor) for vendor in nic_vendors]
    nic_vendors = SelectMultipleField("NIC Vendors:", choices=nic_vendors_choices)
    nic_speed_operator = SelectField(
        "NIC Speed Operator:",
        choices=[("", ""), ("eq", "=="), ("ne", "!="), ("gt", ">"), ("lt", "<"), ("gte", ">="), ("lte", "<=")],
    )
    nic_speed_value = IntegerField("NIC Speed (Gbps):", validators=[validators.Optional()])
