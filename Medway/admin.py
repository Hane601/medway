from django.contrib import admin, messages
from django import forms
from django.shortcuts import render
from django.http import HttpResponse
from django.utils.timezone import now
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from datetime import date
from reportlab.lib.units import cm
from django.urls import path

from .models import (
    Route,
    Drivers,
    Supplier,
    Representative,
    Monthly_sales,
    Product,
    Store,
    StoreProduct,
    Vehicle,
    jobs,
    Sale,
    SaleItem,
    Expenses,
)

from .forms import ProductAdminForm


# --------------------------------------------------
# BASIC REGISTRATIONS
# --------------------------------------------------
admin.site.register(Route)
admin.site.register(Drivers)
admin.site.register(Supplier)


# --------------------------------------------------
# INLINE MODELS
# --------------------------------------------------
class StoreProductInline(admin.TabularInline):
    model = StoreProduct
    extra = 1
    fields = ("product", "quantity")
    autocomplete_fields = []


class MonthlySalesInline(admin.TabularInline):
    model = Monthly_sales
    extra = 0


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ("job", "amount", "description")


# --------------------------------------------------
# REPRESENTATIVE ADMIN
# --------------------------------------------------
@admin.register(Representative)
class RepresentativeAdmin(admin.ModelAdmin):
    inlines = [MonthlySalesInline]


# --------------------------------------------------
# STORE ADMIN
# --------------------------------------------------

@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ["name",]
    inlines = [StoreProductInline]


# --------------------------------------------------
# PRODUCT ADMIN (ONLY ONE — IMPORTANT)
# --------------------------------------------------
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductAdminForm
    list_display = ("Name", "Supplier")
    search_fields = ("Name",)


# --------------------------------------------------
# VEHICLE ADMIN
# --------------------------------------------------
@admin.register(Vehicle)
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

                    if main_stock and main_stock.quantity < obj.quantity:
                        messages.error(
                            request,
                            f"❌ Not enough stock in Main Store for {obj.product.Name}"
                        )
                        return

                    if main_stock:
                        main_stock.quantity -= obj.quantity
                        main_stock.save()

                obj.save()

        super().save_related(request, form, formsets, change)


# --------------------------------------------------
# JOBS FORM
# --------------------------------------------------
class JobsForm(forms.ModelForm):
    class Meta:
        model = jobs
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        rep = cleaned_data.get("rep")
        driver = cleaned_data.get("driver")
        vehicle = cleaned_data.get("Vehicle")

        qs = jobs.objects.exclude(id=self.instance.id)

        if qs.filter(rep=rep).exists():
            raise forms.ValidationError(f"❌ Rep {rep} already assigned")

        if qs.filter(driver=driver).exists():
            raise forms.ValidationError(f"❌ Driver {driver} already assigned")

        if qs.filter(Vehicle=vehicle).exists():
            raise forms.ValidationError(f"❌ Vehicle {vehicle} already assigned")

        return cleaned_data


# --------------------------------------------------
# JOBS ADMIN
# --------------------------------------------------
@admin.register(jobs)
class JobsAdmin(admin.ModelAdmin):
    readonly_fields = ("sale",)
    exclude = ("cos", "profit",)

    # ---------------- USE CUSTOM TEMPLATE ----------------
    change_form_template = "admin/jobs_change_form.html"

    # ---------------- CHANGE VIEW ----------------
    def change_view(self, request, object_id, form_url='', extra_context=None):
        obj = self.get_object(request, object_id)

        if request.method == "POST" and "end_job" in request.POST:
            
            # Collect expenses from POST
            expenses = []
            idx = 0
            while request.POST.get(f"expense_amount_{idx}") != None:

                value = request.POST.get(f"expense_name_{idx}")
                amount = request.POST.get(f"expense_amount_{idx}")
                print(amount)
                if value and amount:
                    expenses.append((value, float(amount)))
                    idx += 1

            # Save Expenses to DB
            for name, amount in expenses:
                Expenses.objects.create(name=name, amount=amount, job=obj)

            # Update representative sales
            rep = obj.rep
            if rep:
                rep.Sales += obj.sale
                rep.save()

            # Update monthly sales
            month = date.today().strftime("%Y-%m")
            monthlysale, created = Monthly_sales.objects.get_or_create(
                Rep=rep,
                month=month,
            )

            monthlysale.sales += int(obj.sale)
            monthlysale.save()

            # Create Sale & SaleItem
            sale, _ = Sale.objects.get_or_create(
                Date=now().date(),
                defaults={"total_sales": 0},
            )
            SaleItem.objects.create(
                sale=sale,
                job=obj,
                amount=obj.sale,
                description=f"{obj.rep} | {obj.route}",
            )
            sale.total_sales += obj.sale
            sale.save()

            # Return vehicle stock to main store
            self._return_vehicle_stock(request, obj)

            # Generate PDF with collected expenses
            response = self._generate_pdf(obj, expenses)

            # Delete the job after PDF is generated
            obj.delete()
            return response

        return super().change_view(
            request, object_id, form_url, extra_context
        )

    # ---------------- VEHICLE STOCK RETURN ----------------
    def _return_vehicle_stock(self, request, job):
        main_store = Store.objects.filter(name__icontains="main").first()
        if not main_store:
            messages.warning(request, "⚠️ Main Store not found!")
            return

        vehicle_stocks = StoreProduct.objects.filter(vehical=job.Vehicle)
        for v_stock in vehicle_stocks:
            if v_stock.quantity <= 0:
                continue
            main_stock, _ = StoreProduct.objects.get_or_create(
                store=main_store,
                product=v_stock.product,
                defaults={"quantity": 0}
            )
            main_stock.quantity += v_stock.quantity
            main_stock.save()
            v_stock.delete()
        messages.success(request, f"✅ Vehicle stock returned to Main Store for Job {job.id}")

    # ---------------- PDF GENERATION ----------------
    def _generate_pdf(self, job, expenses):
        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename=Job_Report_{job.id}.pdf'

        c = canvas.Canvas(response, pagesize=A4)
        width, height = A4
        y = height - 2 * cm

        # ----- HEADER -----
        c.setFont("Helvetica-Bold", 20)
        c.drawString(2 * cm, y, "JOB REPORT")
        y -= 1.5 * cm

        c.setFont("Helvetica", 12)
        c.drawString(2 * cm, y, f"Job ID: {job.id}")
        y -= 0.7 * cm
        c.drawString(2 * cm, y, f"Date: {datetime.now().strftime('%Y-%m-%d')}")
        y -= 1 * cm

        # ----- JOB DETAILS -----
        c.setFont("Helvetica-Bold", 14)
        c.drawString(2 * cm, y, "Job Details")
        y -= 0.8 * cm

        c.setFont("Helvetica", 12)
        c.drawString(2 * cm, y, f"Representative: {job.rep}")
        y -= 0.6 * cm
        c.drawString(2 * cm, y, f"Driver: {job.driver}")
        y -= 0.6 * cm
        c.drawString(2 * cm, y, f"Vehicle: {job.Vehicle}")
        y -= 0.6 * cm
        c.drawString(2 * cm, y, f"Route: {job.route}")
        y -= 1 * cm

        # ----- SALES -----
        c.setFont("Helvetica-Bold", 14)
        c.drawString(2 * cm, y, "Sales Summary")
        y -= 0.8 * cm

        c.setFont("Helvetica", 12)
        c.drawString(2 * cm, y, f"Total Sale Amount: Rs {job.sale}")
        y -= 0.6 * cm
        c.drawString(2 * cm, y, f"Cost of Sales (COS): Rs {job.cos}")
        y -= 1 * cm

        # ----- EXPENSES -----
        c.setFont("Helvetica-Bold", 14)
        c.drawString(2 * cm, y, "Expenses")
        y -= 0.8 * cm

        total_expense = 0
        c.setFont("Helvetica", 12)
        if expenses:
            for name, amount in expenses:
                c.drawString(2.5 * cm, y, f"- {name}: Rs {amount}")
                total_expense += float(amount)
                y -= 0.5 * cm
        else:
            c.drawString(2.5 * cm, y, "No expenses recorded")
            y -= 0.5 * cm
        y -= 0.5 * cm

        # ----- PROFIT CALCULATION -----
        gross_profit = float(job.sale) - float(job.cos)
        net_profit = gross_profit - total_expense

        c.setFont("Helvetica-Bold", 14)
        c.drawString(2 * cm, y, "Profit Calculation")
        y -= 0.8 * cm

        c.setFont("Helvetica", 12)
        c.drawString(2 * cm, y, f"Gross Profit: Rs {gross_profit}")
        y -= 0.6 * cm
        c.drawString(2 * cm, y, f"Total Expenses: Rs {total_expense}")
        y -= 0.6 * cm
        c.setFont("Helvetica-Bold", 12)
        c.drawString(2 * cm, y, f"Net Profit: Rs {net_profit}")
        y -= 1 * cm

        # ----- FOOTER -----
        c.setFont("Helvetica-Oblique", 9)
        c.drawString(2 * cm, 1.5 * cm, "Generated by Medway Marketing System")

        c.showPage()
        c.save()
        return response
        

# --------------------------------------------------
# ADMIN TITLES
# --------------------------------------------------
admin.site.site_header = "Medway Marketing Administration"
admin.site.site_title = "Medway Marketing Admin"
admin.site.index_title = "Welcome to Medway Marketing Admin Panel"
