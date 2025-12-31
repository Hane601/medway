from django.contrib import admin, messages
from django import forms
from django.shortcuts import render
from django.utils.timezone import now
from django.http import HttpResponse
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from .models import Representative
from .models import (
    Route, Drivers, Vehicle, Supplier, Representative,
    jobs, Product, Store, StoreProduct, Sale, Expenses, SaleItem, Monthly_sales
)
from django.db.models import F
from django.utils.timezone import now
from datetime import date


admin.site.site_header = "Medway Marketing Administration"
admin.site.site_title = "Medway Marketing Admin"
admin.site.index_title = "Welcome to Medway Marketing Admin Panel"

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

class Monthly_salesInline(admin.TabularInline):
    model = Monthly_sales
    fields = ['month', 'sales']
    extra = 0


@admin.register(Representative)
class Representative(admin.ModelAdmin):
    inlines = [Monthly_salesInline]

@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    inlines = [StoreProductInline]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['Name', 'Supplier']
    search_fields = ['Name', 'Supplier']


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ("job", "amount", "description")


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("Date", "total_sales")
    inlines = [SaleItemInline]


# ------------------ VEHICLE ADMIN ------------------
class VehicleAdmin(admin.ModelAdmin):
    inlines = [StoreProductInline]

    def save_related(self, request, form, formsets, change):
        for formset in formsets:
            instances = formset.save(commit=False)
            for obj in instances:
                main_store = Store.objects.filter(name__icontains="main").first()
                if main_store:
                    main_stock = StoreProduct.objects.filter(
                        store=main_store, product=obj.product
                    ).first()
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


# ------------------ JOBS FORM ------------------
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


# ------------------ JOBS ADMIN ------------------
@admin.register(jobs)
class JobsAdmin(admin.ModelAdmin):
    form = JobsForm
    readonly_fields = ['sale']
    exclude = ('cos', 'profit')

    def save_model(self, request, obj, form, change):
        if jobs.objects.filter(route=obj.route).exists():
            messages.warning(request, f"⚠️ Route {obj.route} is already assigned!")
        super().save_model(request, obj, form, change)

    # ------------------ CUSTOM DELETE ------------------
    def delete_view(self, request, object_id, extra_context=None):
        obj = self.get_object(request, object_id)
        if request.method == 'POST':
            expenses = []

            # Gather expenses
            for key, value in request.POST.items():
                if key.startswith('expense_name_'):
                    number = key.split('_')[-1]
                    expense_name = value
                    amount_key = f'expense_amount_{number}'
                    amount = request.POST.get(amount_key)
                    if expense_name and amount:
                        expenses.append((expense_name, float(amount)))

            # Save expenses
            for name, amount in expenses:
                Expenses.objects.create(name=name, amount=amount, job=obj)

            #update rep sale
            rep = obj.rep  
            
            if rep:
                rep.Sales += obj.sale
                rep.save()

            job_date = now().date()  # or use obj.Date if you have a date field for the job
            month_start = str(job_date.replace(day=1))  # normalize to the first day of the month
            print(month_start)

            if rep:
                monthly_sale, created = Monthly_sales.objects.get_or_create(
                    Rep=rep,
                    month=month_start[:-3],
                    defaults={'sales': 0}
                )
                # Add job sale to monthly sales
                monthly_sale.sales += obj.sale
                monthly_sale.save() 

            # Save or update Sale entry
            sale, _ = Sale.objects.get_or_create(
                Date=datetime.now().date(),
                defaults={"total_sales": 0}
            )
            SaleItem.objects.create(
                sale=sale,
                job=obj,
                amount=obj.sale,
                description=f"Rep={obj.rep}, Driver={obj.driver}, Route={obj.route}"
            )
            sale.total_sales += obj.sale
            sale.save()

            # Move remaining vehicle stock to Main Store
            self.move_vehicle_stock_to_main_store(request, obj)

            # Generate PDF report
            response = self.generate_pdf(obj, expenses)

            # Delete the job
            obj.delete()

            return response

        context = dict(self.admin_site.each_context(request), object=obj)
        return render(request, 'admin/custom_delete_form.html', context)

    # ------------------ VEHICLE STOCK RETURN ------------------
    def move_vehicle_stock_to_main_store(self, request, job):
        main_store = Store.objects.filter(name__icontains="main").first()
        if not main_store:
            messages.error(request, "⚠️ Main Store not found!")
            return

        vehicle_stocks = StoreProduct.objects.filter(vehical=job.Vehicle)
        if not vehicle_stocks.exists():
            messages.warning(request, "⚠️ No stock found in vehicle")
            return

        for v_stock in vehicle_stocks:
            if v_stock.quantity <= 0:
                continue
            main_stock, _ = StoreProduct.objects.get_or_create(
                store=main_store,
                product=v_stock.product,
                defaults={'quantity': 0}
            )
            main_stock.quantity += v_stock.quantity
            main_stock.save()
            v_stock.delete()

        messages.success(request, f"✅ Vehicle stock returned to Main Store for Job {job.id}")

    # ------------------ PDF GENERATION ------------------
    def generate_pdf(self, job, expenses):
        filename = f"media/job reports/Job_Report_{job.id}.pdf"
        c = canvas.Canvas(filename, pagesize=A4)

        # Job Header
        c.setFont("Helvetica-Bold", 22)
        c.drawString(70, 800, f"JOB REPORT - ID: {job.id}")

        # Job Details
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, 760, "Job Details:")
        c.setFont("Helvetica", 12)
        c.drawString(70, 740, f"Rep: {job.rep}")
        c.drawString(70, 720, f"Driver: {job.driver}")
        c.drawString(70, 700, f"Vehicle: {job.Vehicle}")
        c.drawString(70, 680, f"Route: {job.route}")
        c.drawString(70, 660, f"Sale Amount: Rs {job.sale}")

        # Expenses
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, 630, "Expenses:")
        y = 610
        total_expense = 0
        c.setFont("Helvetica", 12)
        for name, amount in expenses:
            c.drawString(70, y, f"• {name}: Rs {amount}")
            total_expense += amount
            y -= 20

        # Financial Summary
        gross_profit = float(job.sale) - float(job.cos)
        net_profit = gross_profit - float(total_expense)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y - 70, "Financial Summary:")
        c.setFont("Helvetica", 12)
        c.drawString(70, y - 100, f"Sale Amount: Rs {job.sale}")
        c.drawString(70, y - 120, f"Direct cost: Rs {job.cos}")
        c.drawString(70, y - 140, f"Gross Profit: Rs {gross_profit}")
        c.drawString(70, y - 160, f"Total Expenses: Rs {total_expense}")
        c.drawString(70, y - 180, f"Net profit: Rs {net_profit}")

        c.save()

        with open(filename, 'rb') as pdf:
            response = HttpResponse(pdf.read(), content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename=Job_Report_{job.id}.pdf'
            return response
