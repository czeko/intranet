# -*- coding: utf-8 -*-
import os
import base64
import mimetypes
import json

from pyramid.view import view_config
from pyramid.exceptions import Forbidden
from pyramid.httpexceptions import HTTPFound, HTTPNotFound
from pyramid.response import Response

from intranet3.utils.views import BaseView
from intranet3.models import User, Team, DBSession
from intranet3.forms.user import UserEditForm
from intranet3.log import INFO_LOG
from intranet3 import helpers as h
from intranet3.api.preview import Preview
# from intranet3.forms.user import UserListFilterForm


LOG = INFO_LOG(__name__)

class TeamChoices(object):
    def __iter__(self):
        teams = DBSession.query(Team.id, Team.name).order_by(Team.name)
        yield '', u'-- None --'
        for team in teams:
            yield str(team.id), team.name

@view_config(route_name='user_list', permission='freelancer')
class List(BaseView):
    @classmethod
    def user_to_json(cls, user):
        levels_list = [str(users) for users in user.levels_list]
        return json.dumps(dict(
            name=user.name,
            groups=levels_list + user.groups,
            location=user.location,
            start_work=user.start_work.strftime('%d/%m/%Y') if user.start_work else '',
            # team=[]
        ))
    def get(self):
        location= [('poznan', u'Poznań'), ('wroclaw', u'Wrocław')]
        groups = [
            (1, 'INTERN'),
            (2, 'P1'),
            (4, 'P2'),
            ('8', 'P3'),
            ('16', 'P4'),
            ('32', 'FED'),
            ('64', 'ADMIN'),
            ('128', 'Expert zew.'),
            ('256', 'Android Dev'),
            ('512', 'Tester'),
            ('1024', 'CEO\'s Assistant'),
            ('2048', 'CEO'),
            ('user', 'user'),
            ('coordinator', 'coordinator'),
            ('scrum', 'scrum'),
            ('cron', 'cron'),
            ('admin', 'admin'),
        ]
        # form = UserListFilterForm()

        res = DBSession.query(User).order_by(User.name).all()
        users = [user for user in res if user.is_active and not user.client and not user.freelancer]
        freelancers = [user for user in res if user.freelancer and user.is_active]
        team = self.session.query(Team).all()
        clients = []
        inactive = []
        if self.request.has_perm('admin'):
            clients = [user for user in res if user.client and user.is_active]
            inactive = [user for user in res if not user.is_active]


        return dict(
            users=users,
            freelancers=freelancers,
            clients=clients,
            inactive=inactive,
            user_to_json=self.user_to_json,
            team=TeamChoices(),
            locations=location,
            groups=groups
        )


@view_config(route_name='user_view')
class View(BaseView):
    def get(self):
        user_id = self.request.GET.get('user_id')
        user = User.query.get(user_id)
        return dict(user=user)


@view_config(route_name='user_edit', permission='freelancer')
class Edit(BaseView):

    def dispatch(self):
        user_id = self.request.GET.get('user_id')

        if user_id and self.request.has_perm('admin'):
            user = User.query.get(user_id)
        elif user_id:
            raise Forbidden()
        else:
            user = self.request.user
        form = UserEditForm(self.request.POST, obj=user)
        if self.request.method == 'POST' and form.validate():
            user.availability_link = form.availability_link.data or None
            user.tasks_link = form.tasks_link.data or None
            user.skype = form.skype.data or None
            user.phone = form.phone.data or None
            user.phone_on_desk = form.phone_on_desk.data or None
            user.irc = form.irc.data or None
            user.location = form.location.data or None
            user.start_work = form.start_work.data or None
            user.description = form.description.data or None
            if form.level.data:
                user.levels = reduce(lambda x,y:x|y,[int(x) for x in form.level.data])
            if self.request.has_perm('admin'):
                user.is_active = form.is_active.data
                groups = form.groups.data
                if "freelancer" in groups:
                    groups.remove('freelancer')
                    user.freelancer = True
                else:
                    user.freelancer = False
                user.groups = groups
                user.start_full_time_work = form.start_full_time_work.data or None
            user.is_programmer = form.is_programmer.data
            user.is_frontend_developer = form.is_frontend_developer.data
            user.is_graphic_designer = form.is_graphic_designer.data


            if form.avatar.data:
                preview = Preview(self.request)
                if not preview.swap_avatar(type='users', id=user.id):
                    self.flash(self._(u"No preview to swap"))

            self.flash(self._(u"User data saved"))
            LOG(u"User data saved")
            if user_id and self.request.has_perm('admin'):
                return HTTPFound(location=self.request.url_for('/user/edit', user_id=user_id))
            else:
                return HTTPFound(location=self.request.url_for('/user/edit'))

        if user.freelancer:
            form.groups.data = user.groups + ['freelancer']
        return dict(id=user.id, user=user, form=form)


@view_config(route_name='user_tooltip', permission='freelancer')
class Tooltip(BaseView):
    def get(self):
        user_id = self.request.GET.get('user_id')
        user = User.query.get(user_id)
        return dict(user=user)


def _avatar_path(user_id, settings, temp=False):
    user_id = str(user_id)
    if temp:
        return os.path.join(settings['AVATAR_PATH'], 'previews', user_id)
    return os.path.join(settings['AVATAR_PATH'], 'users', user_id)


@view_config(route_name='user_avatar', permission='freelancer')
class Avatar(BaseView):
    def _file_read(self, path):
        if os.path.exists(path):
            try:
                f = open(path)
                data = f.read()
                f.close()
                return data
            except IOError as e:
                LOG(e)
        return None


    def _avatar(self, user_id, temp=False):
        return self._file_read(_avatar_path(user_id, self.request.registry.settings, temp))

    def _response(self, data):
        if data is None:
            raise HTTPNotFound()
        else:
            response = Response(data)
            response.headers['Content-Type'] = 'image/png'
            return response

    def get(self):
        user_id = self.request.GET.get('user_id')
        data = self._avatar(user_id)
        if data is None:
            path = os.path.normpath(os.path.join(os.path.dirname(__file__),'..','static','img','anonymous.png'))
            data = self._file_read(path)
        return self._response(data)

