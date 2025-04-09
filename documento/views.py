from django.db import connection
from django.shortcuts import render

# Create your views here.
def list(request):
    return render(request, 'documento/listDoc.html')

