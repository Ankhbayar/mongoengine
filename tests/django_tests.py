# -*- coding: utf-8 -*-

import unittest

from mongoengine import *

from django.template import Context, Template
from django.conf import settings
import datetime
settings.configure(DEBUG = True)

class QuerySetTest(unittest.TestCase):

    def setUp(self):
        connect(db='mongoenginetest')

        class Person(Document):
            name = StringField()
            age = IntField()
        self.Person = Person
        class Post(Document):
            title = StringField()
            ymd = StringField() # Year Month Day 20110616 for Prefix filter
            is_published = BooleanField()
            author = ReferenceField(self.Person)
            created_at = DateTimeField()
            order = IntField()
            meta = {
                'ordering': ['+order']
            }
            def save(self, *args, **kargs):
                self.ymd = self.created_at.strftime("%Y-%m-%d")
                super( Post, self).save(*args, **kargs)
        self.Post = Post 

    def test_order_by_in_django_template(self):
        """Ensure that QuerySets are properly ordered in Django template.
        """
        self.Person.drop_collection()

        self.Person(name="A", age=20).save()
        self.Person(name="D", age=10).save()
        self.Person(name="B", age=40).save()
        self.Person(name="C", age=30).save()

        t = Template("{% for o in ol %}{{ o.name }}-{{ o.age }}:{% endfor %}")

        d = {"ol": self.Person.objects.order_by('-name')}
        self.assertEqual(t.render(Context(d)), u'D-10:C-30:B-40:A-20:')
        d = {"ol": self.Person.objects.order_by('+name')}
        self.assertEqual(t.render(Context(d)), u'A-20:B-40:C-30:D-10:')
        d = {"ol": self.Person.objects.order_by('-age')}
        self.assertEqual(t.render(Context(d)), u'B-40:C-30:A-20:D-10:')
        d = {"ol": self.Person.objects.order_by('+age')}
        self.assertEqual(t.render(Context(d)), u'D-10:A-20:C-30:B-40:')

        self.Person.drop_collection()

    def test_order_by_in_django_template(self):

        self.Person.drop_collection()

        self.Person(name="A", age=20).save()
        self.Person(name="D", age=10).save()
        self.Person(name="B", age=40).save()
        self.Person(name="C", age=30).save()

        t = Template("{% for o in ol %}{{ o.name }}-{{ o.age }}:{% endfor %}")

        d = {"ol": self.Person.objects.filter(Q(age=10) | Q(name="C"))}
        self.assertEqual(t.render(Context(d)), u'D-10:C-30:')

    def test_q_with_complex_condition_in_template(self):

        self.Person.drop_collection()
        self.Post.drop_collection()

        # Authors
        bob = self.Person.objects.create(name="Bob", age=25)
        jon = self.Person.objects.create(name="Jon", age=27)

        # Bob do this
        self.Post.objects.create(title="bob #1", author = bob, is_published = True, created_at = datetime.datetime(2011,5,28 ), order = 1 ) # Finished
        self.Post.objects.create(title="bob #2", author = bob, is_published = False, created_at = datetime.datetime(2011,6,5 ), order = 2 ) # Draft
        self.Post.objects.create(title="bob #3", author = bob, is_published = True, created_at = datetime.datetime(2011,6,1 ), order = 3 ) # Finished

        # Jon do this
        self.Post.objects.create(title="jon #1", author = jon, is_published = True, created_at = datetime.datetime(2011,5,28 ), order = 4 ) # Finished
        self.Post.objects.create(title="jon #2", author = jon, is_published = True, created_at = datetime.datetime(2011,6,5 ), order = 5 ) # Finished
        self.Post.objects.create(title="jon #3", author = jon, is_published = True, created_at = datetime.datetime(2011,6,1 ), order = 6 ) # Finished 
        # Jon is Good :)

        t = Template("{% for p in posts %}{{ p.title }}|{% endfor %}")

        # Jon is Works
        d = {"posts": self.Post.objects.filter(author = jon )}
        self.assertEqual(t.render(Context(d)), u'jon #1|jon #2|jon #3|')

        # Bob is Works
        d = {"posts": self.Post.objects.filter(author = bob )}
        self.assertEqual(t.render(Context(d)), u'bob #1|bob #2|bob #3|')

        # Finished Works Jon & Bob
        d = {"posts": self.Post.objects.filter(Q(author = bob ) | Q(author = jon ) ).filter( is_published = True  )}
        self.assertEqual(t.render(Context(d)), u'bob #1|bob #3|jon #1|jon #2|jon #3|')

        # Finished Works Jon & Bob in Jun
        d = {"posts": self.Post.objects.filter(Q(author = bob ) | Q(author = jon ) ).filter( is_published = True ).filter(ymd__startswith = "2011-06" )}
        self.assertEqual(t.render(Context(d)), u'bob #3|jon #2|jon #3|')

        # Jon & Bob all works 
        d = {"posts": self.Post.objects.filter(Q(author = bob ) | Q(author = jon ) )}
        self.assertEqual(t.render(Context(d)), u'bob #1|bob #2|bob #3|jon #1|jon #2|jon #3|')

        # All works in May & Jun without order
        d = {"posts": self.Post.objects.filter(Q(ymd__startswith = "2011-05" ) | Q(ymd__startswith = "2011-06" ) )}
        self.assertEqual(t.render(Context(d)), u'bob #1|bob #2|bob #3|jon #1|jon #2|jon #3|')
        
        # All works in May & Jun
        d = {"posts": self.Post.objects.filter(Q(ymd__startswith = "2011-05" ) | Q(ymd__startswith = "2011-06" ) ).order_by("+order")} # Boom! #185
        self.assertEqual(t.render(Context(d)), u'bob #1|bob #2|bob #3|jon #1|jon #2|jon #3|')

        # Jon & Bob all works 
        p = Paginator(objects, 2) # 2 per page
        d = {"posts": self.Post.objects.filter(Q(author = bob ) | Q(author = jon ) )}
        self.assertEqual(t.render(Context(d)), u'bob #1|bob #2|bob #3|jon #1|jon #2|jon #3|')

        # With paginator
        from django.core.paginator import Paginator
        # Finished Works Jon & Bob in Jun
        objects = self.Post.objects.filter(Q(author = bob ) | Q(author = jon ) ).filter( is_published = True , ymd__startswith = "2011-06" )
        p = Paginator(objects, 2) # 2 per page

        # First page
        d = {"posts": p.page(1).object_list }
        self.assertEqual(t.render(Context(d)), u'bob #3|jon #2|')

        # Second page
        d = {"posts": p.page(2).object_list }
        self.assertEqual(t.render(Context(d)), u'jon #3|')
