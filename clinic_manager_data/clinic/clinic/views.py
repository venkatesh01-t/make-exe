
@login_required(login_url='accounts:login')
def inventory_partial(request):
    return render(request, 'partials/inventory.html')
