from django.shortcuts import render
from django.template import loader
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import authenticate, login
from .models import jobs, Representative, Products

def login_user(request):
    if request.method == 'POST':
        password = request.POST.get('Password')
        NIC = request.POST.get('NIC')
        ongoing_jobs = jobs.objects.all()

        try: 
            Representative.objects.get(Nic = NIC, password = password)
            for job in ongoing_jobs:
                if job.rep.Nic == NIC:
                    messages.success(request, 'You successfully logged in.')
                    return redirect('rep_view', NIC=NIC)
            else:
                messages.error(request, 'No jobs ongoing')
        except:
            messages.error(request, 'Invalid NIC or password')

    return render(request, 'home.html')


def rep_view(request, NIC):
	products = Products.objects.all()
	return render(request, 'rep_view.html', {'products': products})

