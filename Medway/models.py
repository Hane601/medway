from django.db import models
from django.contrib.auth.models import AbstractUser

class Representative(models.Model):
	Name = models.CharField(max_length=100)
	Nic = models.CharField(max_length=12, unique=True)
	Phone = models.CharField(max_length=10)
	Address = models.CharField(max_length=255)
	password = models.CharField(max_length=15)

	def __str__(self):
		return f"{self.Name}{'\u00A0\u00A0\u00A0'}{'\u00A0\u00A0\u00A0'}{self.Nic}"

class Supplier(models.Model):
    name = models.CharField(max_length=255, unique=True)
    contact_info = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

class Products(models.Model):
	Name = models.CharField(max_length=500)
	Barcode_no = models.CharField(max_length=20)
	Buying_price = models.CharField(max_length=7)
	Supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)
	Selling_price = models.CharField(max_length=7)

	def __str__(self):
		return f"{self.Name}"

class Route(models.Model):
	Name = models.CharField(max_length=500)
	Route_no = models.CharField(max_length=20)

	def __str__(self):
		return f"{self.Name}{'\u00A0\u00A0\u00A0'}{'\u00A0\u00A0\u00A0'}{self.Route_no}"

class Vehicals(models.Model):
	Vehical_type = models.CharField(max_length=500)
	Vehical_no = models.CharField(max_length=20)

	def __str__(self):
		return f"{self.Vehical_type}{'\u00A0\u00A0\u00A0'}{'\u00A0\u00A0\u00A0'}{self.Vehical_no}"

class Drivers(models.Model):
	Name = models.CharField(max_length=500)
	Nic = models.CharField(max_length=12)
	Phone = models.CharField(max_length=10)
	Address = models.CharField(max_length=500)

	def __str__(self):
		return f"{self.Name}{'\u00A0\u00A0\u00A0'}{'\u00A0\u00A0\u00A0'}{self.Nic}"

class Main_store(models.Model):
	product = models.ForeignKey(Products, on_delete=models.CASCADE)
	quantity = models.IntegerField()

	def __str__(self):
		return f"{self.product}{'\u00A0\u00A0\u00A0'}{'\u00A0\u00A0\u00A0'}{self.quantity}"

class jobs(models.Model):
	rep = models.ForeignKey(Representative, on_delete=models.CASCADE)
	driver = models.ForeignKey(Drivers, on_delete=models.CASCADE)
	Vehical = models.ForeignKey(Vehicals, on_delete=models.CASCADE)
	Route = models.ForeignKey(Route, on_delete=models.CASCADE)

	def __str__(self):
		return f"{self.Vehical} {'\u00A0\u00A0\u00A0'} {self.rep} {'\u00A0\u00A0\u00A0'} {self.driver}"



