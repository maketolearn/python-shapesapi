"""
This module provides a direct interface with the Digital Object Repository.
See http://www.dorepository.org/ for more information.

Currently the only authentication method supported is Basic Authentication.
In order for this module to function, you must create another file in the
same directory called ``settings.py`` which contains the following::
    
    DO_USER = username
    DO_PASSWORD = password
    DO_URL = http://example.com:8810/do/

Create a digital object in the repository by using the ``create`` method of a ``DigitalObjectRepository`` 
object. Creating a DigitalObject object does *not* create a record in the repository.

You use the DigitalObject record to get and set attributes using the ``set`` and ``get`` methods.

Add a file to a digital object using the ``put_file`` method of the DigitalObject object. 
Creating a DigitalObjectFile object does *not* create a record in the repository.

To retrieve a given stored file as a file object (which you can read), use the `get_file` method of 
the DigitalObject object.

You can retrieve all digital objects by calling the ``all`` method on a ``DigitalObjectRepository`` object.
You can search by calling the ``search`` method on a ``DigitalObjectRepository`` object.

>>> rep = DigitalObjectRepository(settings.DO_URL)
>>> old_all_objects = rep.all()
>>> old_matching_objects = rep.search('objatt_name:"Test Object"')
>>> do = rep.create(data = {'name': "Test Object", 'creator': "Jordan Reiter" }) # only way to create a DO
>>> handle = do.handle 
>>> do.get('name')
'Test Object'
>>> do.set('language', 'Python')
>>> do.get('language')
'Python'
>>> file = open('/tmp/samplefile.txt', 'w')
>>> file.write("Sample content.")
>>> file.close()
>>> do.put_file('example', "/tmp/samplefile.txt")
>>> do = None
>>> do
>>> do = rep.get(handle)
>>> do.handle == handle
True
>>> dof = do.files['example']
>>> print dof
<DigitalObjectFile samplefile.txt (text/plain)>
>>> dof.body
'Sample content.'
>>> fo = do.get_file('example')
>>> fo.read()
'Sample content.'
>>> dof.save("/tmp/samplefile2.txt")
>>> copy = open("/tmp/samplefile2.txt")
>>> copy.read()
'Sample content.'
>>> new_all_objects = rep.all()
>>> new_matching_objects = rep.search('objatt_name:"Test Object"')
>>> len(new_all_objects) - len(old_all_objects)
1
>>> len(new_matching_objects) - len(old_matching_objects)
1
>>> do.delete()
>>> final_all_objects = rep.all()
>>> final_matching_objects = rep.search('objatt_name:"Test Object"')
>>> len(final_all_objects) - len(old_all_objects)
0
>>> len(final_matching_objects) - len(old_matching_objects)
0
"""    

import urllib2, urllib, base64, datetime, mimetypes, sys, os, time
from StringIO import StringIO
import poster

try:
    import lxml.etree as ET
    ET.fromstring('<root><parent name="senior"><child name="junior" /></parent></root>').findall('.//child[@name="junior"]')
except (ImportError, SyntaxError):
    try:
        import xml.etree.cElementTree as ET
        ET.fromstring('<root><parent name="senior"><child name="junior" /></parent></root>').findall('.//child[@name="junior"]')
    except ImportError:
        import xml.etree.ElementTree as ET

try:
    ET.fromstring('<root><parent name="senior"><child name="junior" /></parent></root>').findall('.//child[@name="junior"]')
except SyntaxError:
    raise Exception("Can't run server on this machine. You need to have a ElementTree module that supports XPath queries.")

import settings

poster.streaminghttp.register_openers()

class DORepositoryException(Exception):
    pass

class DigitalObjectNotFound(DORepositoryException):
    pass

class DORepositoryServerError(DORepositoryException):
    def __init__(self, reason=None):
        self.reason = reason

    def __str__(self):
        return "".join([
                       "Bad request (probably do to incorrect value in settings.DO_URL)",
                       " :%s" % self.reason if self.reason else "" 
                       ])
 

class DORepositoryConnectionError(DORepositoryException):
    def __init__(self, reason=None):
        self.reason = reason

    def __str__(self):
        return "".join([
                       "Request to repository failed",
                       " :%s" % self.reason if self.reason else "" 
                       ])

NONSTANDARD_MIME_TYPES = {
    'svg': 'image/svg+xml',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
}
def guess_type(filename):
    guess = mimetypes.guess_type(filename)[0]
    if not guess:
        guess = NONSTANDARD_MIME_TYPES.get(filename.split('.')[-1], 'application/octet-stream')
    return guess
        

def escape_for_url(s):
    return urllib.quote_plus(s).replace('%3A',':').replace('%29',')').replace('%28','(')

def parse_objects(data, url):
    result = []
    doc = ET.fromstring(data)
    for doobj in doc.findall('do'):
        obj = {}
        handle = doobj.get('id')
        obj['handle'] = handle
        obj['url'] = '%s%s/' % (url, escape_for_url(handle))
        attlist = doobj.findall('att')
        if attlist:
            createdms = int(doobj.findall("att[@name='internal.created']")[0].get('value'))
            obj['created'] = datetime.datetime.fromtimestamp(createdms/1000)
            data = {}
            for a in attlist:
                if 'internal.' in a:
                    continue
                data[a.get('name')]=a.get('value')
            obj['attributes']=data
            obj['files']={}
            for el in doobj.findall('el'):
                fo = {}
                key = el.get('id')
                if 'internal.' in key:
                    continue
                for a in el.getchildren():
                    if a.tag != 'att':
                        continue
                    if a.get('name') == 'internal.size':
                        fo['size']=a.get('value')
                    if 'internal.' in a.get('name'):
                        continue
                    fo[a.get('name')]=a.get('value')
                fo['url'] = '%(url)s%(handle)s/el/%(key)s' % { 'url': url, 'handle': escape_for_url(handle), 'key': escape_for_url(key) }
                obj['files'][key]=fo
        result.append(obj)
    return result

def parse_object(data, url):
    result = {}
    doc = ET.fromstring(data)
    doobj = doc.findall('do')[0]
    handle = doobj.get('id')
    result['handle'] = handle
    result['url'] = '%s%s/' % (url, escape_for_url(handle))
    createdms = int(doobj.findall("att[@name='internal.created']")[0].get('value'))
    result['created'] = datetime.datetime.fromtimestamp(createdms/1000)
    data = {}
    for e in doobj.findall('att'):
        key = e.get('name')
        if 'internal.' not in key:
            data[key]=e.get('value')
    result['attributes']=data
    result['files']={}
    for el in doobj.findall('el'):
        fo = {}
        key = el.get('id')
        if 'internal.' in key:
            continue
        for a in el.getchildren():
            if a.get('name') == 'internal.size':
                fo['size']=a.get('value')
            if 'internal.' in a.get('name'):
                continue
            fo[a.get('name')]=a.get('value')
        fo['url'] = '%(url)s%(handle)s/el/%(key)s' % { 'url': url, 'handle': escape_for_url(handle), 'key': escape_for_url(key) }
        result['files'][key]=fo
    return result 

def get_file_container(file):
    file_container = {}
    try:
        try:
            file=open(file,'r')
        except TypeError:
            file.seek(0)
        file_container['body']=file.read()
        file_container['filename']=os.path.basename(file.name)
        ct = guess_type(file.name)
        if ct:
            file_container['mimetype']=ct
    except AttributeError:
        file_container['filename']=file['filename']
        file_container['mimetype']=file['content_type']
        file_container['body']=file['body']
    return file_container



class RequestWithMethod(urllib2.Request):
    def __init__(self, method, *args, **kwargs):
        self._method = method
        urllib2.Request.__init__(self, *args, **kwargs)

    def get_method(self):
        return self._method



class AuthenticatedRequest(RequestWithMethod):
    def __init__(self, username, password, *args, **kwargs):
        RequestWithMethod.__init__(self, *args, **kwargs)
        auth = base64.encodestring('%s:%s' % (username, password))[:-1] # This is just standard un/pw encoding  
        self.add_header('Authorization', 'Basic %s' % auth ) # Add Auth header to request


class AuthorizedOpener(object):
    """
    This code creates a request with basic authentication
    """
    def __init__(self, username=None, password=None):
        self.username = username
        self.password = password
        self.requests = 0
        self.errors = 0

    def _make_request(self, url, files=None, data=None, body=None, method='GET'):
        assert(body == None or (data == None and files == None)) # if body is given, files and data must be empty  
        params = data or {}
        if files:
            for n, f in files.items():
                params[n] = f[0]['body']
        headers = {}
        if params:
            data, headers = poster.encode.multipart_encode(params)
        elif body:
            data = body
        self.request = AuthenticatedRequest(self.username, self.password, method, url, data=data, headers=headers)
        try:
            self.response = urllib2.urlopen(self.request)
            self.requests += 1
        except urllib2.URLError:
            self.errors += 1
            raise
            
    def get(self, url):
        self._make_request(url, method='GET')
    
    def post(self, url, files=None, data=None, body=None):
        self._make_request(url, files=files, data=data, body=body, method='POST')
    
    def put(self, url, files=None, data=None, body=None):
        self._make_request(url, files=files, data=data, body=body, method='PUT')
    
    def put_file(self, url, file=None):
        data = file['body']
        headers = {}
        self.request = AuthenticatedRequest(self.username, self.password, 'PUT', url, data=data, headers=headers)
        self.response = urllib2.urlopen(self.request)        
    
    def delete(self, url):
        self._make_request(url, method='DELETE')
    
    def read(self):
        return self.response.read()

    @property
    def headers(self):
        return self.response.headers



class DigitalObjectFile(object):
    def __init__(self, digital_object=None, url=None, filename=None, mimetype=None, body=None, size=None):
        self.digital_object = digital_object
        self.url = url
        if filename:
            self.filename = filename
        if mimetype:
            self.mimetype = mimetype
        if size:
            self.size = size
        if body:
            self.body = body

    @property
    def mimetype(self):
        if not hasattr(self,'_mimetype'):
            self._mimetype = guess_type(self.filename)
        return self._mimetype
    
    @mimetype.setter
    def mimetype(self, value):
        self._mimetype = value

    @property
    def filename(self):
        if not hasattr(self,'_filename'):
            return 'Untitled'
        return self._filename
    
    @filename.setter
    def filename(self, value):
        self._filename = value

    def __str__(self):
        name = self.filename or 'Untitled'
        return "<DigitalObjectFile %s (%s)>" % (name, self.mimetype)
    
    def open(self):
        return StringIO(self.body)
    
    def save(self, file):
        """
        Save the digital object file to an actual file.
        
        You can send it a file object or a filename.
        """
        try:
            file = open(file, 'w')
        except TypeError:
            pass
        file.write(self.body)
        file.close()
    
    @property
    def body(self):
        if not hasattr(self, '_body'):
            opener.get(self.url)
            self._body = opener.read()
        return self._body

    @body.setter
    def body(self, body):
        self._body = body

class NoDefault(object):
    """ This is a placer object so that if someone specifies a default, 
    even None, it will work
    """
    pass

class DigitalObjectList(object):
    def __init__(self, objects, repository):
        self.repository = repository
        self.object_handles=objects
        self.objects = {}
        self.index = 0
    
    def __len__(self):
        return len(self.object_handles)
    
    def __repr__(self):
        result = []
        for handle in self.object_handles:
            result.append(repr(self.get_object(handle)))
        return "[%s]" % ", ".join(result)

    def get_object(self, handle):
        if isinstance(handle, DigitalObject):
            return handle
        obj = self.objects.get(handle, None)
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



class DigitalObject(object):
    def __init__(self, repository=None, url=None, handle=None, created=None, files=[], attributes={}):
        self.repository = repository
        self.url = url
        self.attributes = attributes
        self.handle = handle
        self.created = created
        self.files = {}
        if files:
            for file_key, file_obj in files.items():
                if isinstance(file_obj,DigitalObjectFile):
                    self.files[file_key]=file_obj
                else:
                    self.files[file_key]=DigitalObjectFile(**file_obj)
        
    def __eq__(self, other):
        return other.handle == self.handle

    def __str__(self):
        return self.handle

    def __repr__(self):
        result = []
        result.append('DigitalObject(')
        result.append('{')
        result.append('handle: "%s"' % self.handle)
        result.append(', created: "%s"' % self.created)
        result.append(', attributes: %s' % str(self.attributes))
        result.append(', files: { %s }' % ", ".join(["'%s': %s" % (k, str(v)) for k, v in self.files.items()]))
        result.append(')')
        return "".join(result)
        
    def keys(self):
        return self.attributes.keys()
        
    def get(self, name, default=NoDefault):
        try:
            return self.attributes[name]
        except KeyError:
            if default != NoDefault:
                return default
            raise AttributeError("'%(obj_type)s' has no attribute '%(name)s'. It does have %(what)s" % { 'obj_type': type(self).__name__, 'name': name, 'what': repr(self.__dict__) })

    def set(self, name, value):
        opener.put('%(url)satt/%(name)s/' % {'url': self.url, 'handle': escape_for_url(self.handle), 'name': escape_for_url(name)}, body=value)
        self.attributes[name]=value

    def get_file(self, name):
        return self.files[name].open()
    
    def put_file(self, name, file):
        file = get_file_container(file)
        file_url = '%sel/%s/' % (self.url, name)
        opener.put_file(file_url, file)
        opener.put('%sel/%s/att/mimetype' % (self.url, name), body=file.get('mimetype', guess_type(file['filename'])) )
        opener.put('%sel/%s/att/filename' % (self.url, name), body=file['filename'] )
        file['url'] = file_url
        self.files[name] = DigitalObjectFile(**file)
        
    def delete(self):
        opener.delete(self.url)



class DigitalObjectRepository(object):
    
    def __init__(self, url):
        self.url=url
    
    def requests(self):
        return opener.requests
    
    def search(self, query=''):
        search_url = self.url + '?query=%s' % escape_for_url(query)
        opener.get(search_url)
        object_list = parse_objects(opener.read(), self.url)
        return DigitalObjectList(objects=[DigitalObject(**o) for o in object_list], repository=self)
            
    def all(self):
        opener.get(self.url)
        object_list = parse_objects(opener.read(), self.url)
        return DigitalObjectList(objects=[o['handle'] for o in object_list], repository=self)
    
    def get(self, handle=None):
        url = '%s%s/' % (self.url, escape_for_url(handle))
        try:
            opener.get(url)
        except urllib2.HTTPError, inst:
            if inst.code == 404:
                raise DigitalObjectNotFound("Digital object %s not found in repository." % handle)
            elif inst.code == 400:
                raise DORepositoryServerError(inst.reason)
            else:
                raise
        except urllib2.URLError, inst:
                raise DORepositoryServerError(inst.reason)
        objdata = parse_object(opener.read(), url=self.url)
        do_files = {}
        for k, v in objdata['files'].items():
            do_files[k] = DigitalObjectFile(url=v['url'], filename=v.get('filename', None), mimetype=v.get('mimetype', None), size=v.get('size', None))
        objdata['files'] = do_files
        obj = DigitalObject(repository=self, **objdata)
        return obj
    
    def create(self, files={}, data={}):
        opener.post(self.url)
        objdata = parse_object(opener.read(), url=self.url)
        obj = DigitalObject(repository=self, **objdata)
        for k, v in files.items():
            obj.put_file(k, v)
        for k, v in data.items():
            obj.set(k, v)
        return obj


opener = AuthorizedOpener(settings.DO_USER, settings.DO_PASSWORD)

if __name__ == "__main__":
    import doctest
    doctest.testmod()