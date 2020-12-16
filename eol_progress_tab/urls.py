

from django.conf.urls import url
from django.conf import settings

from .views import EolProgressTabFragmentView
from django.contrib.auth.decorators import login_required


urlpatterns = (
    url(
        r'courses/{}/eol_progress_tab$'.format(
            settings.COURSE_ID_PATTERN,
        ),
        login_required(EolProgressTabFragmentView.as_view()),
        name='eol_progress_tab_view',
    ),
)
