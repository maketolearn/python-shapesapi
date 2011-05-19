"""
This module is a Shape Library wrapper for the DO Repository API
See dorepository.py for more information about the API.

Create a shape by using the ``create`` method of a ``ShapeRepository`` 
object. Creating a Shape object does *not* create a record in the repository.

You use the Shape record to get and set attributes using the ``set`` and ``get`` methods.

Add the file or mask to a shape by setting the ``file`` or ``mask`` properties, respectively of the ``Shape`` object. 
Creating a ShapeFile object does *not* create a record in the repository.

To retrieve a given stored file as a file object (which you can read), use the ``open`` function of the ``ShapeFile`` object.

You can retrieve all shapes by calling the ``all`` method on a ``ShapeRepository`` object.
You can retrieve all categories by calling the ``all`` method on a ``CategoryRepository`` object.

You can search shapes by calling the ``search`` method on a ``ShapeRepository`` object.
You can search categories by calling the ``search`` method on a ``CategoryRepository`` object.

>>> circle_svg = '''<?xml version="1.0" ?><!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd"><svg width="100%" height="100%" version="1.1" xmlns="http://www.w3.org/2000/svg"><circle cx="100" cy="50" r="40" stroke="black" stroke-width="0" fill="red"/></svg>'''
>>> mask_svg = '''<?xml version="1.0" ?><!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd"><svg width="100%" height="100%" version="1.1" xmlns="http://www.w3.org/2000/svg"><circle cx="100" cy="50" r="40" stroke="black" stroke-width="0" fill="black"/></svg>'''
>>> rep = ShapeRepository(repository=DigitalObjectRepository(settings.DO_URL))
>>> old_all_shapes = rep.all()
>>> old_matching_shapes = rep.search('objatt_name:"Test Shape"')
>>> shape = rep.create(name="Test Shape", creator="Jordan Reiter") # only way to create a DO
>>> type(shape).__name__
'Shape'
>>> handle = shape.handle 
>>> shape.name
'Test Shape'
>>> shape.set('format', 'fab@school')
>>> shape.get('format')
'fab@school'
>>> file = open('/tmp/samplefile.svg', 'w')
>>> file.write(circle_svg)
>>> file.close()
>>> mask = open('/tmp/samplefile_mask.svg', 'w')
>>> mask.write(mask_svg)
>>> mask.close()
>>> shape.put_file("/tmp/samplefile.svg")
>>> shape.put_mask("/tmp/samplefile_mask.svg")
>>> shape = None
>>> shape
>>> shape = rep.get(handle)
>>> shape.handle == handle
True
>>> shape_file = shape.file
>>> mask_file = shape.mask
>>> print shape_file
<ShapeFile samplefile.svg (image/svg+xml)>
>>> print mask_file
<ShapeFile samplefile_mask.svg (mask, image/svg+xml)>
>>> shape_file.body
'<?xml version="1.0" ?><!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd"><svg width="100%" height="100%" version="1.1" xmlns="http://www.w3.org/2000/svg"><circle cx="100" cy="50" r="40" stroke="black" stroke-width="0" fill="red"/></svg>'
>>> mask_file.body
'<?xml version="1.0" ?><!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd"><svg width="100%" height="100%" version="1.1" xmlns="http://www.w3.org/2000/svg"><circle cx="100" cy="50" r="40" stroke="black" stroke-width="0" fill="black"/></svg>'
>>> mask_file_object = mask_file.open()
>>> mask_file_object.read()
'<?xml version="1.0" ?><!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd"><svg width="100%" height="100%" version="1.1" xmlns="http://www.w3.org/2000/svg"><circle cx="100" cy="50" r="40" stroke="black" stroke-width="0" fill="black"/></svg>'
>>> mask_file.save("/tmp/samplefile_mask_copy.svg")
>>> copy = open("/tmp/samplefile_mask_copy.svg")
>>> copy.read()
'<?xml version="1.0" ?><!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd"><svg width="100%" height="100%" version="1.1" xmlns="http://www.w3.org/2000/svg"><circle cx="100" cy="50" r="40" stroke="black" stroke-width="0" fill="black"/></svg>'
>>> new_all_shapes = rep.all()
>>> new_matching_shapes = rep.search('objatt_name:"Test Shape"')
>>> len(new_all_shapes) - len(old_all_shapes)
1
>>> len(new_matching_shapes) - len(old_matching_shapes)
1
>>> shape.delete()
>>> final_all_shapes = rep.all()
>>> final_matching_shapes = rep.search('objatt_name:"Test Shape"')
>>> len(final_all_shapes) - len(old_all_shapes)
0
>>> len(final_matching_shapes) - len(old_matching_shapes)
0"""
import sys
from dorepository import escape_for_url, DigitalObjectRepository, DigitalObject
import settings

NAMESPACE=' xmlns:xlink="http://www.w3.org/1999/xlink"'

class ShapesException(Exception):
    pass

class ShapeNotFound(ShapesException):
    pass

class ShapeInvalidRecord(ShapesException):
    def __init__(self, handle):
        self.handle = handle
        
    def __str__(self):
        return "Record found in the digital object repository for %s, but it is not a shape record!" % self.handle

class MultipleShapesFound(ShapesException):
    pass

class CategoryNotFound(ShapesException):
    pass

class MultipleCategoriesFound(ShapesException):
    pass

class BaseList(object):
    def __init__(self, repository=None, digital_object_list=None, handles=[]):
        self.repository = repository
        self.digital_object_list=digital_object_list
        if self.digital_object_list:
            self.object_handles = self.digital_object_list.object_handles
        else:
            self.object_handles=handles
        self.objects = {}
        self.index = 0
    
    def __len__(self):
        return len(self.object_handles)
    
    def __str__(self):
        return ",".join([str(obj) for obj in self.object_handles])
    
    def __repr__(self):
        result = []
        for handle in self.object_handles:
            result.append(repr(self.get_object(handle)))
        return "<%s [%s]>" % (type(self).__name__, ", ".join(result))

    def get_object(self, handle):
        if isinstance(handle, self.repository.object_cls):
            return handle
        elif isinstance(handle, DigitalObject):
            return self.repository.object_cls(digital_object=handle, repository=self.repository)
        try:
            obj = self.objects.get(handle, None)
        except TypeError:
            raise Exception("We have a %s" % repr(handle))
        if not obj:
            obj = self.repository.get(handle)
            self.objects[handle] = obj
        return obj
    
    def __getitem__(self, index):
        if isinstance(index, slice):
            sliced_list = self.object_handles[index]
            return [self.get_object(handle) for handle in sliced_list]
        else:
            return self.get_object(self.object_handles[index])
    
    def __iter__(self):
        for handle in self.object_handles:
            yield self.get_object(handle)



class ShapeList(BaseList):
    def xml(self, namespace=True, details=True):
        return '<Shapes%(namespace)s>%(shapes)s</Shapes>' % {'namespace': NAMESPACE if namespace else "", 'shapes': "".join([shape.xml(False, details) for shape in self])}



class ShapeFile(object):
    def __init__(self, url=None, do_file=None, type=None):
        self.url = url
        self.do_file = do_file
        self.type = type

    @property
    def body(self):
        return self.do_file.body
    
    def open(self):
        return self.do_file.open()
    
    def save(self, file):
        return self.do_file.save(file)

    def __getattr__(self, name):
        try:
            return getattr(self.do_file, name)
        except:
            raise AttributeError("'%s' object has no attribute '%s'." % (type(self).__name__, name))

    def __repr__(self):
        if self.type:
            return "<%s %s (%s, %s)>" % (type(self).__name__, self.do_file.filename, self.type, self.do_file.mimetype)
        else:
            return "<%s %s (%s)>" % (type(self).__name__, self.do_file.filename, self.do_file.mimetype)

SHAPE_ATTRIBUTES = ['name', 'description', 'classroom', 'creator', 'school', ]
class Shape(object):
    def __init__(self, digital_object, repository):
        self.digital_object = digital_object
        self.repository = repository

    def __getattr__(self, name):
        try:
            return getattr(self.digital_object, name)
        except AttributeError:
            if name in SHAPE_ATTRIBUTES:
                return self.digital_object.get(name)
            else:
                raise AttributeError("'%s' object has no attribute '%s'" % (type(self).__name__, name))
    def __settattr__(self, name):
        if name in SHAPE_ATTRIBUTES:
            return self.digital_object.set(name)
        else:
            raise AttributeError("'%s' object has no attribute '%s'" % (type(self).__name__, name))

    def add_category(self, category):
        self.categories.add(category)
        self.digital_object.set('category', str(self.categories))
    
    @property
    def url(self):
        return settings.SHAPE_URL % escape_for_url(self.digital_object.handle)

    @property
    def mask(self):
        mask_digital_file_object = self.digital_object.files.get('mask', None)
        if mask_digital_file_object:
            return ShapeFile(type='mask', do_file=mask_digital_file_object, url=settings.MASK_URL % escape_for_url(self.handle))
        else:
            return None

    @property
    def file(self):
        digital_file_object = self.digital_object.files.get('content', None)
        if digital_file_object:
            return ShapeFile(do_file=digital_file_object, url=settings.FILE_URL % escape_for_url(self.handle))
        else:
            return None

    @property
    def categories(self):
        if not hasattr(self, '_categories'):
            category_list = self.get('category',"")
            if category_list:
                self._categories = CategoryList(repository = CategoryRepository(url=self.repository.url), handles=category_list.split(','))
            else:
                self._categories = CategoryList(repository = CategoryRepository(url=self.repository.url))
        return self._categories      

    def xml(self, namespace=True, details=True):
        xml = []
        xml.append('<Shape name="%(name)s" created="%(created)s" id="%(handle)s"%(namespace)s xlink:href="%(link)s"' % {
            'name': self.name,
            'created': self.created,
            'handle': self.handle,
            'namespace': NAMESPACE if namespace else '',
            'link': self.url
        })
        if details:
            xml.append('>')
            if self.file:
                xml.append('<File xlink:href="%(url)s" type="%(type)s" name="%(name)s" />' % {
                                                                                             'url': self.file.url,
                                                                                             'type': self.file.mimetype,
                                                                                             'name': self.file.filename
                                                                                             })
            if self.mask:
                xml.append('<Mask xlink:href="%(url)s" type="%(type)s" name="%(name)s" />' % {
                                                                                             'url': self.mask.url,
                                                                                             'type': self.mask.mimetype,
                                                                                             'name': self.mask.filename
                                                                                             })
            if self.categories:
                xml.append(self.categories.xml(False))
            xml.append("</Shape>")
        else:
            xml.append(" />")
        return "".join(xml)
        
    

    def put_file(self, file, label='content'):
        self.digital_object.put_file(label, file)

    def put_mask(self, file):
        self.put_file(file, 'mask')
        
    def delete(self):
        self.digital_object.delete()

class ShapeRepository(object):
    object_cls = Shape
    
    def __init__(self, repository=None, url=None):
        self.repository = repository or DigitalObjectRepository(url)
        self.url = url or self.repository.url

    def search(self, query_string='', categories=None):
        query = []
        if query_string:
            query.append(query_string)
        if categories:
            cat_query = []
            for cat in categories:
                try:
                    cat_query.append("objatt_category:%s" % cat.handle)
                except AttributeError:
                    cat_query.append("objatt_category:%s" % cat)
            query.append("(%s)" % "".join(cat_query))
        query = "objatt_type:shape AND (%s)" % (" AND ".join(query))
        return ShapeList(digital_object_list=self.repository.search(query), repository=self)
            
    def all(self):
        return ShapeList(digital_object_list=self.repository.search("objatt_type:shape"), repository=self)
    
    def get(self, handle=None):
        digital_object = self.repository.get(handle=handle)
        if digital_object.get('type') == 'shape':
            return Shape(digital_object=digital_object, repository=self)
        else:
            raise ShapeInvalidRecord(handle)
    
    def create(self, name=None, file=None, mask=None, categories=[], **kwargs):
        data = kwargs
        files = {}
        if file:
            files['content'] = file
        if mask:
            files['mask'] = mask
        if categories:
            category_list = CategoryList(names=[cat for cat in categories if cat], repository=CategoryRepository(repository=self.repository))
            data['category'] = str(category_list)
        data['name'] = name
        data['type'] = 'shape'
        digital_object = self.repository.create(files=files, data=data)
        return Shape(digital_object=digital_object, repository=self)



class CategoryList(BaseList):
    def __init__(self, repository=None, names=None, handles=None, *args, **kwargs):
        super(CategoryList, self).__init__(repository=repository, *args, **kwargs)
        if names:
            for name in names:
                self.add(name)
    
    def add(self, obj):
        if obj not in self.object_handles:
            if not isinstance(obj, Category):
                category_object = self.repository.create(obj)
            else:
                category_object = obj
            self.objects[category_object.handle] = category_object
            self.object_handles.append(category_object.handle)

    def xml(self, namespace=True, details=False):
        return "<Categories%(namespace)s>%(cats)s</Categories>" % {'namespace': NAMESPACE if namespace else "", 'cats': "".join(cat.xml(False, details) for cat in self)}


class Category(object):
    def __init__(self, digital_object=None, repository=None):
        self.digital_object = digital_object
        self.repository = repository
        
    def __getattr__(self, name):
        try:
            return getattr(self.digital_object, name)
        except:
            raise AttributeError("'%s' object has no attribute '%s'" % (type(self).__name__, name))
        
    @property
    def url(self):
        return settings.CATEGORY_URL % escape_for_url(self.digital_object.handle)

    def get(self, name):
        return self.digital_object.get(name)
    
    def set(self, name, value):    
        return self.digital_object.set(name, value)
        
    @property
    def name(self):
        """Get the category name"""
        return self.get('name')

    @property
    def children(self):
        if not hasattr(self, '_children'):
            self._children = ShapeRepository(url=self.repository.url).search(categories=[self])
        return self._children 

    def xml(self, namespace=True, details=False):
        xml = []
        xml.append('<Category id="%(handle)s" name="%(name)s"' % {
                                                                  'handle': self.digital_object.handle, 
                                                                  'name': self.name,
                                                                  })
        if namespace:
            xml.append(' xmlns:xlink="http://www.w3.org/1999/xlink"')
        xml.append(' xlink:href="%(link)s"' % {
                                               'link': self.url
                                               })
        if details:
            xml.append('>')
            if self.children:
                xml.append(self.children.xml(False, False))
            xml.append('</Category>')
        else:
            xml.append(' />')
        return "".join(xml)



class CategoryRepository(object):
    """
    A repository object used for retrieving categories from the DO Repository
    """
    object_cls=Category
    
    def __init__(self, repository=None, url=None):
        self.repository = repository or DigitalObjectRepository(url)
        self.url = url or self.repository.url

    def search(self, query=''):
        """
        do a search of the repository, filtered by type=category
        """
        return CategoryList(digital_object_list=self.repository.search('objatt_type:category AND (%s)' % query), repository=self)
            
    def all(self):
        """
        do a search of the repository for all objects with type=category
        """
        return CategoryList(digital_object_list=self.repository.search('objatt_type:category'), repository=self)
    
    def get(self, name):
        """
        Searches the repository for objects of type category with either the name or id matching the input.
        Because categories must be unique, it throws an error if more than one matching category is found.
        Returns a Category object
        """
        exact_matches = []
        for result in self.search(query="id:%(handle)s OR objatt_name:%(name)s" % {'handle': name, 'name': name }):
            if result.name == name or result.handle == name:
                exact_matches.append(result)
        if not exact_matches:
            raise CategoryNotFound("\nNo category found for %s" % name)
        if len(exact_matches) > 1:
            raise MultipleCategoriesFound("More than one category found for %s" % name)
        return exact_matches[0]

    def get_or_create(self, category):
        """
        Searches the repository for a matching category. If none is found, it creates a new one.
        It returns a tuple of (Category, boolean) where the second item is true if the category was created.
        Returns a Category object
        """
        try:
            return self.get(category), False
        except CategoryNotFound:
            digital_object = self.repository.create(data={'name': category, 'type': 'category'})
            return Category(digital_oject=digital_object, repository=self.repository), True

    def create(self, name=None):
        """
        Because we don't want to create duplicate categories, we always call get_or_create instead.
        """
        obj, _ = self.get_or_create(name)
        return obj


if __name__ == "__main__":
    import doctest
    doctest.testmod()