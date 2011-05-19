import tornado.ioloop
import tornado.web
import os

import settings, shapes

class MethodNotAllowed(tornado.web.HTTPError):
    def __init__(self, method=None, *args, **kwargs):
        super(MethodNotAllowed,self).__init__(405, "Method %s not allowed", [method], *args, **kwargs)

class ShapeHandler(tornado.web.RequestHandler):
    def prepare(self, *args, **kwargs):
        self.repository = shapes.ShapeRepository(url=settings.DO_URL)

    def get(self, handle=None, *args):
        if handle:
            self.write(self.repository.get(handle).xml(True))
        else:
            self.write(self.repository.all().xml(True))
        self.set_header('Content-Type', "text/xml")
            

    def put(self, *args):
        raise tornado.web.HTTPError(405, "Method %s not allowed", ("PUT",))
    
    def post(self, *args):
        name = self.request.arguments['name'][0]
        creator = self.request.arguments['creator'][0]
        school = self.request.arguments['school'][0]
        categories = self.request.arguments.get('category', [])
        try:
            file =  self.request.files['file'][0]
        except:
            raise tornado.web.HTTPError(400, "File not provided. You must include a file when creating a shape.")
        mask = None
        if self.request.files.has_key('mask'):
            mask =  self.request.files['mask'][0]
        shape = self.repository.create(name=name, file=file, mask=mask, categories=categories, creator=creator, school=school)
        resp = shape.xml(True)
        self.set_status(201)
        self.set_header('Content-Type', 'text/xml')
        self.set_header('Location', shape.url)
        self.write(resp)

    def delete(self, handle=None, *args):
        if not self.request.arguments.get('seriously',False):
            raise tornado.web.HTTPError(405, "Method %s not allowed", ("DELETE",))
        shape = self.repository.get(handle)
        shape.delete()

class ShapeFormHandler(tornado.web.RequestHandler):
    def prepare(self, *args, **kwargs):
        self.cat_repository = shapes.CategoryRepository(url=settings.DO_URL)
    
    def get(self):
        categories = self.cat_repository.all()
        self.render('templates/shape.html', categories=categories)

    def put(self, *args):
        raise tornado.web.HTTPError(405, "Method %s not allowed", ("PUT",))

    def post(self, *args):
        raise tornado.web.HTTPError(405, "Method %s not allowed", ("POST",))

    def delete(self, handle=None):
        if not self.request.arguments.get('seriously',False):
            raise tornado.web.HTTPError(405, "Method %s not allowed", ("DELETE",))
        shape = self.repository.get(handle)
        shape.delete()
            

class ShapeFileHandler(tornado.web.RequestHandler):
    def prepare(self, *args, **kwargs):
        self.repository = shapes.ShapeRepository(url=settings.DO_URL)
        
    def get(self, handle):
        shape = self.repository.get(handle)
        self.write(shape.file.body)
        self.set_header('Content-Type', shape.file.mimetype)

    def put(self, *args):
        raise tornado.web.HTTPError(405, "Method %s not allowed", ("PUT",))

    def post(self, *args):
        raise tornado.web.HTTPError(405, "Method %s not allowed", ("POST",))

    def delete(self, *args):
        raise tornado.web.HTTPError(405, "Method %s not allowed", ("DELETE",))

class ShapeMaskHandler(tornado.web.RequestHandler):
    def prepare(self, *args, **kwargs):
        self.repository = shapes.ShapeRepository(url=settings.DO_URL)
        
    def get(self, handle):
        shape = self.repository.get(handle)
        try:
            self.write(shape.mask.body)
        except Exception, inst:
            raise tornado.web.HTTPError(404, 'Mask not found for shape %s (%s)' % (handle, repr(inst)))
        self.set_header('Content-Type', shape.file.mimetype)

    def put(self, *args):
        raise tornado.web.HTTPError(405, "Method %s not allowed", ("PUT",))

    def post(self, *args):
        raise tornado.web.HTTPError(405, "Method %s not allowed", ("POST",))

    def delete(self, *args):
        raise tornado.web.HTTPError(405, "Method %s not allowed", ("DELETE",))


class CategoryHandler(tornado.web.RequestHandler):
    def prepare(self, *args, **kwargs):
        self.cat_repository = shapes.CategoryRepository(url=settings.DO_URL)

    def get(self, handle=None, *args):
        if handle:
            self.write(self.cat_repository.get(handle).xml(True, details=True))
        else:
            self.write(self.cat_repository.all().xml(True))
        self.set_header('Content-Type', "text/xml")

    def put(self, *args):
        raise tornado.web.HTTPError(405, "Method %s not allowed", ("PUT",))

    def post(self, *args):
        name = self.request.arguments['name'][0]
        category, created = self.cat_repository.get_or_create(name)
        self.write(category.xml(True))
        self.set_header('Content-Type', 'text/xml')
        if created:
            self.set_header('Location', category.url)
            self.set_status(201)

    def delete(self, *args):
        raise tornado.web.HTTPError(405, "Method %s not allowed", ("DELETE",))
    
class CategoryFormHandler(tornado.web.RequestHandler):
    
    def get(self):
        self.render('templates/category.html')

    def put(self, *args):
        raise tornado.web.HTTPError(405, "Method %s not allowed", ("PUT",))

    def post(self, *args):
        raise tornado.web.HTTPError(405, "Method %s not allowed", ("POST",))

    def delete(self, *args):
        raise tornado.web.HTTPError(405, "Method %s not allowed", ("DELETE",))



application = tornado.web.Application([
    (r"/shapes/entry/?", ShapeFormHandler),
    (r"/shapes/file/([^/]+)?/?", ShapeFileHandler),
    (r"/shapes/mask/([^/]+)?/?", ShapeMaskHandler),
    (r"/shapes/([^/]+)?/?", ShapeHandler),
    (r"/cats/entry/?", CategoryFormHandler),
    (r"/cats/([^/]+)?/?", CategoryHandler),
])

if __name__ == "__main__":
    application.listen(settings.PORT, settings.HOST)
    tornado.ioloop.IOLoop.instance().start()
    
