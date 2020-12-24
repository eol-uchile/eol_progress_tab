

from django.conf.urls import url
from django.conf import settings

from .views import EolProgressTabFragmentView, get_course_info, get_student_data
from django.contrib.auth.decorators import login_required


urlpatterns = (
    url(
        r'courses/{}/eol_progress_tab$'.format(
            settings.COURSE_ID_PATTERN,
        ),
        login_required(EolProgressTabFragmentView.as_view()),
        name='eol_progress_tab_view',
    ),
    url(
        r'courses/{}/eol_progress_tab/course_info$'.format(
            settings.COURSE_ID_PATTERN,
        ),
        login_required(get_course_info),
        name='eol_progress_tab_course_info',
    ),
    url(
        r'courses/{}/eol_progress_tab/student_data$'.format(
            settings.COURSE_ID_PATTERN,
        ),
        login_required(get_student_data),
        name='eol_progress_tab_student_data',
    ),
)
