# -*- coding: utf-8 -*-


from mock import patch, Mock

from django.test import TestCase, Client
from django.urls import reverse

from util.testing import UrlResetMixin
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase

from xmodule.modulestore.tests.factories import CourseFactory, ItemFactory
from capa.tests.response_xml_factory import StringResponseXMLFactory
from student.tests.factories import UserFactory, CourseEnrollmentFactory
from student.roles import CourseStaffRole

from lms.djangoapps.grades.course_grade_factory import CourseGradeFactory

from . import views

import datetime
from six import text_type


class TestEolProgressTabView(UrlResetMixin, ModuleStoreTestCase):
    def setUp(self):
        super(TestEolProgressTabView, self).setUp()
        # create a course
        self.course = CourseFactory.create(org='mss', course='999',
                                           display_name='eol progress tab')

        # Patch the comment client user save method so it does not try
        # to create a new cc user when creating a django user
        with patch('student.models.cc.User.save'):
            # Create the student
            self.student = UserFactory(username='student', password='test', email='student@edx.org')
            # Enroll the student in the course
            CourseEnrollmentFactory(user=self.student, course_id=self.course.id)

            # Create and Enroll staff user
            self.staff_user = UserFactory(username='staff_user', password='test', email='staff@edx.org', is_staff=True)
            CourseEnrollmentFactory(user=self.staff_user, course_id=self.course.id)
            CourseStaffRole(self.course.id).add_users(self.staff_user)

            # Log the student in
            self.client = Client()
            self.assertTrue(self.client.login(username='student', password='test'))

            # Log the user staff in
            self.staff_client = Client()
            self.assertTrue(self.staff_client.login(username='staff_user', password='test'))

        # Give course some content (1 chapter, 2 category grades, 3 sections)
        with self.store.bulk_operations(self.course.id, emit_signals=False):
            chapter = ItemFactory.create(
                parent_location=self.course.location,
                category="sequential",
            )
            # Homework
            section = ItemFactory.create(
                parent_location=chapter.location,
                category="sequential",
                metadata={'graded': True, 'format': 'Homework'}
            )
            self.items = [
                ItemFactory.create(
                    parent_location=section.location,
                    category="problem",
                    data=StringResponseXMLFactory().build_xml(answer='foo'),
                    metadata={'rerandomize': 'always'}
                )
                for __ in range(5)
            ]
            # Homework_2
            section_2 = ItemFactory.create(
                parent_location=chapter.location,
                category="sequential",
                metadata={'graded': True, 'format': 'Homework_2'}
            )
            self.items_2 = [
                ItemFactory.create(
                    parent_location=section_2.location,
                    category="problem",
                    data=StringResponseXMLFactory().build_xml(answer='foo'),
                    metadata={'rerandomize': 'always'}
                )
                for __ in range(5)
            ]
            # Homework_2
            section_3 = ItemFactory.create(
                parent_location=chapter.location,
                category="sequential",
                metadata={'graded': True, 'format': 'Homework_2'}
            )
            self.items_2 = [
                ItemFactory.create(
                    parent_location=section_3.location,
                    category="problem",
                    data=StringResponseXMLFactory().build_xml(answer='foo'),
                    metadata={'rerandomize': 'always'}
                )
                for __ in range(5)
            ]

    @patch("eol_progress_tab.views._has_page_access")
    def test_render_page(self, has_page_access):
        """
            Test correct render page with an IFrame
        """
        has_page_access.side_effect = [True]
        url = reverse('eol_progress_tab_view',
                      kwargs={'course_id': self.course.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn( 'id="reactIframe"', response.content.decode("utf-8"))

    def test_grade_percent_scaled(self):
        """
            Test scale percent grades. 
        """
        # 0.03 <= grade_cutoff <= 0.97
        test_cases = [[.0, .6, 1.], [.4, .4, 4.], [1., .97, 7.], [.7, .6, 4.8], [.3, .6, 2.5]]  # [grade_percent, grade_cutoff, grade_scaled]
        for tc in test_cases:
            grade_scaled = views._grade_percent_scaled(tc[0], tc[1])
            self.assertEqual(grade_scaled, tc[2])

    def test_format_date(self):
        """
            Test format date into correct string
        """
        date = datetime.datetime(2021, 1, 11)
        format_date = views._format_date(date)
        self.assertEqual(format_date, '2021-01-11T00:00:00')

    def test_get_course_dates(self):
        """
            Test get course dates
        """
        # default data
        course_start_date, course_end_date = views._get_course_dates(self.course)
        self.assertEqual(course_start_date, None)
        self.assertEqual(course_end_date, None)

        # set course start/end
        self.course.start = datetime.datetime(2021, 1, 11)
        self.course.end = datetime.datetime(2021, 1, 20)
        course_start_date, course_end_date = views._get_course_dates(self.course)
        self.assertEqual(course_start_date, '2021-01-11T00:00:00')
        self.assertEqual(course_end_date, '2021-01-20T00:00:00')

    def test_prominent_section_filter(self):
        """
            Test filter sections with prominent key
        """
        # section breakdown w/ example data
        section_breakdown = [
            {
                "category":"PRUEBA 1",
                "label":"P1 01",
                "detail":"PRUEBA 1 1 - Subsección 3 - 60% (3/5)",
                "percent":0.6
            },
            {
                "category":"PRUEBA 1",
                "label":"P1 02",
                "detail":"PRUEBA 1 2 - Subsección 11 - 50% (1/2)",
                "percent":0.5
            },
            {
                "category":"PRUEBA 1",
                "label":"P1 Promedio",
                "prominent":True, # 1
                "detail":"PRUEBA 1 Promedio = 55%",
                "percent":0.55
            },
            {
                "category":"PRUEBA 2",
                "label":"P2 01",
                "detail":"PRUEBA 2 1 - Subsección 7 - 100% (1/1)",
                "percent":1.0
            },
            {
                "category":"PRUEBA 2",
                "label":"P2 02",
                "mark":{
                    "detail":"Los puntajes más bajos 1 PRUEBA 2 se descartan."
                },
                "detail":"PRUEBA 2 2 - Subsección 9 - 50% (1/2)",
                "percent":0.5
            },
            {
                "category":"PRUEBA 2",
                "label":"P2 Promedio",
                "prominent":True, # 2
                "detail":"PRUEBA 2 Promedio = 100%",
                "percent":1.0
            },
            {
                "category":"PRUEBA 3",
                "label":"P3",
                "prominent":True, # 3
                "detail":"PRUEBA 3 = 0%",
                "percent":0.0
            }
        ]
        student_category_grades = filter(views._prominent_section_filter, section_breakdown)
        self.assertEqual(len(list(student_category_grades)), 3) # new length should be 3.

    @patch("eol_progress_tab.views.get_cert_data")
    def test_get_certificate_data(self, get_cert_data):
        """
            Test get certificate data.
            Mock get_cert_data from `from lms.djangoapps.courseware.views.views import _get_cert_data`
        """
        cert_data = Mock()
        cert_data.cert_web_view_url = 'url'
        cert_data.title = 'title'
        cert_data.msg = 'msg'
        get_cert_data.side_effect = [cert_data]

        certificate_data = views._get_certificate_data(self.student, self.course, 'honor', {} )
        self.assertNotEqual(certificate_data, {}) # validate is not empty
        self.assertEqual(certificate_data['url'], 'url') # validate url

    def test_get_subsection_url(self):
        """
            Test get subsection url with edX jump_to
        """
        url = views._get_subsection_url('location', self.course.id)
        self.assertIn(text_type(self.course.id), url)
        self.assertIn('location', url)
        self.assertIn('jump_to', url)

    def test_get_category_scores_detail(self):
        """
            Test get category scores details
            On test setup we create the course w/ some content (Homework & Homework_2).
        """
        course_grade = CourseGradeFactory().read(self.user, self.course)
        category_scores_detail = views._get_category_scores_detail(course_grade, self.course.id)
        self.assertTrue('HOMEWORK' in category_scores_detail)
        self.assertTrue('HOMEWORK_2' in category_scores_detail)
        self.assertEqual(len(category_scores_detail['HOMEWORK']), 1) # Homework has one section
        self.assertEqual(len(category_scores_detail['HOMEWORK_2']), 2) # Homework_2 has two sections

    @patch("eol_progress_tab.views._has_page_access")
    def test_get_course_info(self, has_page_access):
        """
            Test get course info request
            Verify if response has the important keys
        """
        has_page_access.side_effect = [True]
        url = reverse('eol_progress_tab_course_info',
                      kwargs={'course_id': self.course.id})
        response = self.client.get(url)
        data = response.content.decode("utf-8")
        self.assertEqual(response.status_code, 200)
        self.assertTrue( 'grade_cutoff' in data )
        self.assertTrue( 'min_grade_approval' in data )
        self.assertTrue( 'start_date' in data )
        self.assertTrue( 'end_date' in data )
        self.assertTrue( 'effort' in data )
        self.assertTrue( 'display_name' in data )

    @patch("eol_progress_tab.views._has_page_access")
    def test_get_student_data(self, has_page_access):
        """
            Test get student data request
            Verify if response has the important keys
        """
        has_page_access.side_effect = [True]
        url = reverse('eol_progress_tab_student_data',
                      kwargs={'course_id': self.course.id, 'user_id': self.student.id})
        response = self.client.get(url)
        data = response.content.decode("utf-8")
        self.assertEqual(response.status_code, 200)
        data = response.content.decode("utf-8")
        self.assertTrue( 'username' in data )
        self.assertTrue( 'final_grade_percent' in data )
        self.assertTrue( 'final_grade_scaled' in data )
        self.assertTrue( 'passed' in data )
        self.assertTrue( 'certificate_data' in data )
        self.assertTrue( 'category_grades' in data )