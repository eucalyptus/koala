from pyramid.view import view_config
from pyramid.renderers import render_to_response

<<<<<<< HEAD
@view_config(route_name='render_template')
def render_template(request):
    template_name = '/'.join(request.subpath)
    return render_to_response('eucaconsole.templates:{0}.pt'.format(template_name), {}, request=request)
=======

class TagEditorDirectiveView(BaseView):

    @view_config(route_name='tag_editor_template', renderer='../templates/tag-editor/tag-editor.pt')
    def tag_editor_template(self):
        return dict()


class GenericDirectiveView(object):
    """
    This class is to provide views to serve directives where all that's neeeded is i18n
    """
    def __init__(self, request, **kwargs):
        self.request = request
    
    @view_config(route_name='stack_aws_dialogs', renderer='../templates/stacks/stack_aws_dialogs.pt')
    def aws_dialogs_template(self):
        return dict()
>>>>>>> 06673bed79b583fa383ff67e5c7b1a84a122625c
