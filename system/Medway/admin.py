from django.contrib import admin, messages
from django import forms
from django.shortcuts import render
from django.utils.timezone import now
from django.http import HttpResponse
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from .models import (
    Representative, Route, Drivers, Vehicle, Supplier,
    jobs, Product, Store, StoreProduct, Sale, Expenses, SaleItem, Monthly_sales
)
from .forms import ProductAdminForm

# ------------------ BASIC REGISTRATIONS ------------------
admin.site.register(Route)
admin.site.register(Drivers)
admin.site.register(Supplier)

# ------------------ INLINE MODELS ------------------
class StoreProductInline(admin.TabularInline):
    model = StoreProduct
    extra = 1
    fields = ['product', 'quantity']
    autocomplete_fields = ['product']

class MonthlySalesInline(admin.TabularInline):
    model = Monthly_sales
    fields = ['month', 'sales']
    extra = 0

class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ("job", "amount", "description")

# ------------------ REPRESENTATIVE ------------------
@admin.register(Representative)
class RepresentativeAdmin(admin.ModelAdmin):
    inlines = [MonthlySalesInline]

# ------------------ STORE ------------------
@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    #inlines = [StoreProductInline]
    list_display = ['name']

# ------------------ PRODUCT ------------------
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductAdminForm
    list_display = ['Name', 'Supplier']
    search_fields = ['Name', 'Supplier']

# ------------------ SALE ------------------
@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("Date", "total_sales")
    inlines = [SaleItemInline]

# ------------------ VEHICLE ------------------
class VehicleAdmin(admin.ModelAdmin):
    inlines = [StoreProductInline]

    def save_related(self, request, form, formsets, change):
        for formset in formsets:
            instances = formset.save(commit=False)
            for obj in instances:
                main_store = Store.objects.filter(name__icontains="main").first()
                if main_store:
                    main_stock = StoreProduct.objects.filter(store=main_store, product=obj.product).first()
                    if main_stock:
                        if main_stock.quantity < obj.quantity:
                            messages.error(
                                request,
                                f"❌ Not enough stock in Main Store for {obj.product.Name}. Available: {main_stock.quantity}"
                            )
                            return
                        main_stock.quantity -= obj.quantity
                        main_stock.save()
                obj.save()
        super().save_related(request, form, formsets, change)

admin.site.register(Vehicle, VehicleAdmin)

# ------------------ JOBS ------------------
class JobsForm(forms.ModelForm):
    class Meta:
        model = jobs
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        rep = cleaned_data.get("rep")
        driver = cleaned_data.get("driver")
        vehicle = cleaned_data.get("Vehicle")

        existing_jobs = jobs.objects.exclude(id=self.instance.id)
        for job in existing_jobs:
            if job.rep == rep:
                raise forms.ValidationError(f"❌ Rep {rep} is already assigned!")
            if job.driver == driver:
                raise forms.ValidationError(f"❌ Driver {driver} is already assigned!")
            if job.Vehicle == vehicle:
                raise forms.ValidationError(f"❌ Vehicle {vehicle} is already assigned!")
        return cleaned_data

@admin.register(jobs)
class JobsAdmin(admin.ModelAdmin):
    form = JobsForm
    readonly_fields = ['sale']
    exclude = ('cos', 'profit')
    # Your custom save_model, delete_view, etc. can remain here as needed

# ------------------ ADMIN SITE BRANDING ------------------
admin.site.site_header = "Medway Marketing Administration"
admin.site.site_title = "Medway Marketing Admin"
admin.site.index_title = "Welcome to Medway Marketing Admin Panel"
