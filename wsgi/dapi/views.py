# Django modules
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect, Http404
from django.core.urlresolvers import reverse
from django.template import RequestContext
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from taggit.models import Tag

# Our local modules
from dapi.models import Dap, MetaDap, Report
from django.contrib.auth.models import User
from dapi.forms import *
from dapi.logic import *


def index(request):
    '''The homepage, currentl lists top and most ranked daps'''
    top_rated = MetaDap.objects.filter(active=True).order_by('-average_rank', '-rank_count')[:10]
    most_rated = MetaDap.objects.filter(active=True).order_by('-rank_count', '-average_rank')[:10]
    return render(request, 'dapi/index.html', {'top_rated': top_rated, 'most_rated': most_rated})


def tag(request, tag):
    '''Lists all daps of given tag'''
    t = get_object_or_404(Tag, slug=tag)
    all_tagged_daps = MetaDap.objects.filter(tags__slug__in=[tag], active=True).order_by('-average_rank', '-rank_count')
    paginator = Paginator(all_tagged_daps, 25)
    page = request.GET.get('page')
    try:
        daps_list = paginator.page(page)
    except PageNotAnInteger:
        daps_list = paginator.page(1)
    except EmptyPage:
        daps_list = paginator.page(paginator.num_pages)
    return render(request, 'dapi/tag.html', {'daps_list': daps_list, 'tag': t})


@login_required
def upload(request):
    '''Upload a dap form'''
    if request.method == 'POST':
        form = UploadDapForm(request.POST, request.FILES)
        if form.is_valid():
            errors, dname = handle_uploaded_dap(request.FILES['file'], request.user)
            if not errors:
                messages.info(request, 'Dap successfully uploaded.')
                return HttpResponseRedirect(reverse('dapi.views.dap', args=(dname, )))
            else:
                form.errors['file'] = errors
    else:
        form = UploadDapForm()
    return render(request, 'dapi/upload.html', {'form': form})


def dap_devel(request, dap):
    '''Display latest version of dap, even if that's devel'''
    m = get_object_or_404(MetaDap, package_name=dap)
    rank = get_rank(m, request.user)
    reports = m.report_set.filter(solved=False)
    if m.latest:
        return render(request, 'dapi/dap.html', {'metadap': m, 'dap': m.latest, 'similar': m.similar_active_daps()[:5], 'rank': rank, 'reports': reports})
    else:
        raise Http404


def dap_stable(request, dap):
    '''Display latest stable version of dap'''
    m = get_object_or_404(MetaDap, package_name=dap)
    rank = get_rank(m, request.user)
    reports = m.report_set.filter(solved=False)
    if m.latest_stable:
        return render(request, 'dapi/dap.html', {'metadap': m, 'dap': m.latest_stable, 'similar': m.similar_active_daps()[:5], 'rank': rank, 'reports': reports})
    else:
        raise Http404


def dap(request, dap):
    '''Display latest stable version of dap, or latest devel if no stable is available'''
    m = get_object_or_404(MetaDap, package_name=dap)
    rank = get_rank(m, request.user)
    reports = m.report_set.filter(solved=False)
    if m.latest_stable:
        d = m.latest_stable
    elif m.latest:
        d = m.latest
    else:
        d = None
    return render(request, 'dapi/dap.html', {'metadap': m, 'dap': d, 'similar': m.similar_active_daps()[:5], 'rank': rank, 'reports': reports})


def dap_version(request, dap, version):
    '''Display a particular version of dap'''
    m = get_object_or_404(MetaDap, package_name=dap)
    d = get_object_or_404(Dap, metadap=m.pk, version=version)
    rank = get_rank(m, request.user)
    reports = m.report_set.filter(solved=False)
    return render(request, 'dapi/dap.html', {'metadap': m, 'dap': d, 'similar': m.similar_active_daps()[:5], 'rank': rank, 'reports': reports})


@login_required
def dap_admin(request, dap):
    '''Administrate dap's comaintainers, transfer it to other user, (de)activate it or delete it'''
    m = get_object_or_404(MetaDap, package_name=dap)
    if request.user != m.user and not request.user.is_superuser:
        messages.error(request, 'You don\'t have permissions to administrate this dap.')
        return HttpResponseRedirect(reverse('dapi.views.dap', args=(dap, )))
    cform = ComaintainersForm(instance=m)
    tform = TransferDapForm(instance=m)
    aform = ActivationDapForm(instance=m)
    dform = DeleteDapForm()
    if request.method == 'POST':
        if 'cform' in request.POST:
            cform = ComaintainersForm(request.POST, instance=m)
            if cform.is_valid():
                cform.save()
                m.comaintainers.remove(m.user)
                messages.info(request, 'Comaintainers successfully saved.')
                return HttpResponseRedirect(reverse('dapi.views.dap', args=(dap, )))
        if 'tform' in request.POST:
            olduser = m.user
            tform = TransferDapForm(request.POST, instance=m)
            if tform.is_valid():
                if dap == request.POST['verification']:
                    tform.save()
                    m.comaintainers.add(olduser)
                    m.comaintainers.remove(m.user)
                    messages.info(request, 'Dap {dap} successfully transfered.'.format(dap=dap))
                    return HttpResponseRedirect(reverse('dapi.views.dap', args=(dap, )))
                else:
                    tform.errors['verification'] = ['You didn\'t enter the dap\'s name correctly.']
        if 'aform' in request.POST:
            aform = ActivationDapForm(request.POST, instance=m)
            if aform.is_valid():
                if dap == request.POST['verification']:
                    aform.save()
                    messages.info(request, 'Dap {dap} successfully {de}activated.'.format(dap=dap, de='' if m.active else 'de'))
                    return HttpResponseRedirect(reverse('dapi.views.dap', args=(dap, )))
                else:
                    aform.errors['verification'] = ['You didn\'t enter the dap\'s name correctly.']
        if 'dform' in request.POST:
            dform = DeleteDapForm(request.POST)
            if dform.is_valid():
                if dap == request.POST['verification']:
                    m.delete()
                    messages.info(request, 'Dap {dap} successfully deleted.'.format(dap=dap))
                    return HttpResponseRedirect(reverse('dapi.views.index'))
                else:
                    dform.errors['verification'] = ['You didn\'t enter the dap\'s name correctly.']
    return render(request, 'dapi/dap-admin.html', {'cform': cform, 'tform': tform, 'aform': aform, 'dform': dform, 'dap': m})


@login_required
def dap_leave(request, dap):
    '''If you are the comaintainer of a dap, here you resign'''
    m = get_object_or_404(MetaDap, package_name=dap)
    if request.user == m.user:
        messages.error(request, 'You cannot leave this dap. First, transfer it to someone else.')
        return HttpResponseRedirect(reverse('dapi.views.dap', args=(dap, )))
    if not request.user in m.comaintainers.all():
        messages.error(request, 'You cannot leave this dap, you are not it\'s comaintainer.')
        return HttpResponseRedirect(reverse('dapi.views.dap', args=(dap, )))
    if request.method == 'POST':
        form = LeaveDapForm(request.POST)
        if form.is_valid():
            if dap == request.POST['verification']:
                m.comaintainers.remove(request.user)
                messages.info(request, 'Successfully leaved {dap}.'.format(dap=dap))
                return HttpResponseRedirect(reverse('dapi.views.dap', args=(dap, )))
            else:
                form.errors['verification'] = ['You didn\'t enter the dap\'s name correctly.']
    else:
        form = LeaveDapForm()
    return render(request, 'dapi/dap-leave.html', {'form': form, 'dap': m})


@login_required
def dap_version_delete(request, dap, version):
    '''Delete a particular version of a dap'''
    m = get_object_or_404(MetaDap, package_name=dap)
    d = get_object_or_404(Dap, metadap=m.pk, version=version)
    if request.user != m.user and not request.user in m.comaintainers.all() and not request.user.is_superuser:
        messages.error(request, 'You don\'t have permissions to delete versions of this dap.')
        return HttpResponseRedirect(reverse('dapi.views.dap_version', args=(dap, version)))
    if request.method == 'POST':
        form = DeleteVersionForm(request.POST)
        if form.is_valid():
            wrong = False
            if dap != request.POST['verification_name']:
                form.errors['verification_name'] = ['You didn\'t enter the dap\'s name correctly.']
                wrong = True
            if version != request.POST['verification_version']:
                form.errors['verification_version'] = ['You didn\'t enter the version correctly.']
                wrong = True
            if not wrong:
                d.delete()
                messages.info(request, 'Successfully deleted {dap}.'.format(dap=d))
                return HttpResponseRedirect(reverse('dapi.views.dap', args=(dap, )))
    else:
        form = DeleteVersionForm()
    return render(request, 'dapi/dap-version-delete.html', {'form': form, 'dap': d})


@login_required
def dap_tags(request, dap):
    '''Manage dap's tags'''
    m = get_object_or_404(MetaDap, package_name=dap)
    if request.user != m.user and not request.user in m.comaintainers.all() and not request.user.is_superuser:
        messages.error(request, 'You don\'t have permissions to change tags of this dap.')
        return HttpResponseRedirect(reverse('dapi.views.dap', args=(dap, )))
    if request.method == 'POST':
        data = request.POST.copy()
        try:
            data['tags'] = data['tags'].lower() + ','
        except KeyError:
            pass
        form = TagsForm(data, instance=m)
        if form.is_valid():
            form.save()
            messages.info(request, 'Tags successfully saved.')
            return HttpResponseRedirect(reverse('dapi.views.dap', args=(dap, )))
    else:
        form = TagsForm(instance=m)
        if form['tags'].value():
            data = {'tags': ', '.join([tagged.tag.name for tagged in form['tags'].value()])}
            form = TagsForm(data, instance=m)
    return render(request, 'dapi/dap-tags.html', {'form': form, 'dap': m})


@login_required
def dap_rank(request, dap, rank):
    '''Rank a given dap with given rank. Use 0 to unrank.'''
    m = get_object_or_404(MetaDap, package_name=dap)
    rank = int(rank)
    if rank:
        r, c = request.user.rank_set.get_or_create(metadap=m, defaults={'rank': rank})
        if not c:
            r.rank = rank
            r.save()
        messages.info(request, 'Successfully ranked {dap} with {rank}'.format(dap=dap, rank=rank))
    else:
        try:
            request.user.rank_set.get(metadap=m).delete()
        except Rank.DoesNotExist:
            pass
        messages.info(request, 'Successfully unranked {dap}'.format(dap=dap))
    return HttpResponseRedirect(reverse('dapi.views.dap', args=(dap, )))


def dap_report(request, dap):
    '''Report an evil dap'''
    m = get_object_or_404(MetaDap, package_name=dap)
    if request.user.is_authenticated():
        formclass = ReportForm
    else:
        formclass = ReportAnonymousForm
    if request.method == 'POST':
        form = formclass(m, request.POST)
        if form.is_valid():
            r = form.save(commit=False)
            if request.user.is_authenticated():
                r.reporter = request.user
            r.save()
            form.save_m2m()
            if not settings.DEBUG:
                to = []
                if m.user.email:
                    to.append(m.user.email)
                for admin in settings.ADMINS:
                    to.append(admin[1])
                send_mail('Dap {dap} reported as evil'.format(dap=dap),
                          '''Hi, dap {dap} was reported as evil.
                          See {link} for more information.'''.format(dap=dap,
                                                                     link=request.build_absolute_uri(reverse('dapi.views.dap_reports', args=(dap, )))),
                          'no-reply@rhcloud.com',
                          to, fail_silently=False)
            messages.info(request, 'Dap successfully reported.')
            return HttpResponseRedirect(reverse('dapi.views.dap', args=(dap, )))
    else:
        form = formclass(m)
    return render(request, 'dapi/dap-report.html', {'form': form, 'dap': m})


def dap_reports(request, dap):
    '''List reports of given dap'''
    m = get_object_or_404(MetaDap, package_name=dap)
    if request.user.is_staff:
        reports = m.report_set.order_by('solved')
    else:
        reports = m.report_set.filter(solved=False)
    return render(request, 'dapi/dap-reports.html', {'dap': m, 'reports': reports})


@login_required
def report_toggle_solve(request, report_id):
    '''Mark solved reports unsolved and vice versa'''
    if not request.user.is_staff:
        raise Http404
    r = get_object_or_404(Report, id=report_id)
    r.solved = not r.solved
    r.save()
    messages.info(request, 'Successfully toggled the report')
    return HttpResponseRedirect(reverse('dapi.views.dap_reports', args=(r.metadap.package_name, )))


def user(request, user):
    '''Display the user profile'''
    u = get_object_or_404(User, username=user)
    return render(request, 'dapi/user.html', {'u': u})


@login_required
def user_edit(request, user):
    '''Edit the user profile'''
    u = get_object_or_404(User, username=user)
    if request.user.username != user and not request.user.is_superuser:
        messages.error(request, 'You don\'t have permissions to edit this user.')
        return HttpResponseRedirect(reverse('dapi.views.user', args=(user, )))
    uform = UserForm(instance=u)
    pform = ProfileSyncForm(instance=u.profile)
    dform = DeleteUserForm()
    if request.method == 'POST':
        if 'uform' in request.POST:
            uform = UserForm(request.POST, instance=u)
            if uform.is_valid():
                uform.save()
                messages.info(request, 'User successfully saved.')
                return HttpResponseRedirect(reverse('dapi.views.user_edit', args=(u, )))
        if 'pform' in request.POST:
            pform = ProfileSyncForm(request.POST, instance=u.profile)
            if pform.is_valid():
                pform.save()
                messages.info(request, 'Sync settings successfully saved.')
                return HttpResponseRedirect(reverse('dapi.views.user_edit', args=(u, )))
        if 'dform' in request.POST:
            dform = DeleteUserForm(request.POST)
            if dform.is_valid():
                if user == request.POST['verification']:
                    u.delete()
                    messages.info(request, 'Successfully deleted {user}.'.format(user=user))
                    return HttpResponseRedirect(reverse('dapi.views.index'))
                else:
                    dform.errors['verification'] = ['You didn\'t enter the username correctly.']
    return render(request, 'dapi/user-edit.html', {'uform': uform, 'pform': pform, 'dform': dform, 'u': u})


def login(request):
    '''In another world, this would be a log in form.
    Here it just contains backend links.'''
    if request.user.is_authenticated():
        return HttpResponseRedirect(reverse('dapi.views.index'))
    try:
        n = request.GET['next']
    except KeyError:
        n = ''
    return render(request, 'dapi/login.html', {'next': n})


@login_required
def logout(request):
    '''Logs out the user'''
    auth_logout(request)
    return HttpResponseRedirect(reverse('dapi.views.index'))
