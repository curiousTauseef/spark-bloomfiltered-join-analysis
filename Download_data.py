#!/usr/bin/env python3

import json
import itertools
from urllib.request import urlopen
import os
import pathlib


class ApiPart:
    def dependencies(self):
        return []

class ParameterPart(ApiPart):
    def __init__(self, name):
        self.name = name

    def dependencies(self): return [self.name]
    def binded(self, params): return str(params[self.name])
    def __str__(self): return "{" + self.name + "}"

class ConstantPart(ApiPart):
    def __init__(self, value):
        self.value = value

    def binded(self, params): return self.value
    def __str__(self): return self.value


class JSONProvider():
    def __init__(self, path):
        self.path = path.split('.') if type(path) is str else path

    def provide(self, source):
        doc = json.loads(source)
        return self.provideRecur(doc, self.path)

    def provideRecur(self, doc, path):
        if not path:
            if type(doc) is str:
                yield doc
            elif type(doc) in (int, float, bool) or doc is None:
                yield json.dumps(doc)
        if type(doc) is list:
            for element in doc:
                yield from self.provideRecur(element, path)
        if type(doc) is dict and path:
            key, *remainingPath = path
            if key in doc:
                yield from self.provideRecur(doc[key], remainingPath)

class APIUrl:
    def __init__(self, parts, providers={}):
        self.parts = parts
        self.providers = providers

    def dependencies(self):
        return sum((p.dependencies() for p in self.parts), [])

    def provides(self):
        return self.providers.keys()
    
    def binded(self, params):
        return "".join(p.binded(params) for p in self.parts)
    
    def download(self, params):
        url = self.binded(params)
        print("downloading %s..." % (url,))
        return urlopen(url).read().decode('utf-8')
    
    def provide(self, source):
        return dict((
            (param, provider.provide(source))
            for param, provider
            in self.providers.items()
        )) 
        
    def __str__(self):
        return "".join(str(p) for p in self.parts)
    def __repr__(self):
        return "APIUrl('%s')" % (str(self),)

    @staticmethod
    def makePart(e):
        if type(e) is str:
            if e[0] == '{' and e[-1] == '}':
               return ParameterPart(e[1:-1])
            return ConstantPart(e)
        return e

    @staticmethod
    def makeParts(es):
        if type(es) is str: return [APIUrl.makePart(es)]
        else: return [APIUrl.makePart(e) for e in es]

    @staticmethod
    def from_json(endpoint, base=""):
        parts = [ConstantPart(base)] + APIUrl.makeParts(endpoint["url"])
        provides = endpoint.get("provides", {})
        providers = dict((k,JSONProvider(v)) for k,v in provides.items())
        return APIUrl(parts, providers)

def all_param_values(d, pnames):
    params = map(d.get, pnames)
    pvs = itertools.product(*params)
    for x in pvs: yield dict(zip(pnames, x))


class ResultSaver:
    def __init__(self, base="/", extension=".json"):
        self.base = base
        self.extension = extension
    def save(self, url, contents):
        if url.startswith(self.base):
            url = url[len(self.base):]
        if not url.endswith(self.extension):
            url += self.extension
        path = pathlib.Path(url)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('w') as f:
            f.write(contents)


class AllAPI:
    params = {}
    done = set()
    loop = True

    def __init__(self, urls, saver = ResultSaver()):
        self.urls = list(urls)
        self.saver = saver

    def __repr__(self):
        return "AllAPI(%s)" % (self.urls,) 

    def download(self):
        while self.loop: self.download_step()

    def download_step(self):
        self.loop = False
        for url in self.urls: self.download_url(url)

    def download_url(self, url):
        deps = url.dependencies()
        if not set(deps).issubset(self.params.keys()): return
        for url_params in all_param_values(self.params, deps):
            todo = (url, tuple(url_params.values()))
            if todo in self.done: continue
            self.done.add(todo)
            url_str = url.binded(url_params)
            try: result = url.download(url_params)
            except Exception as err:
                print("Download failed on " + url_str)
                print(err)
                continue
            try: self.saver.save(url_str, result)
            except Exception as err:
                print("Save failed on " + url_str)
                print(err)
            try: new_params = url.provide(result)
            except Exception as err:
                print("Parameter provider failed on " + url_str)
                print(err)
                continue
            for param, values in new_params.items():
                prev = self.params.get(param, set())
                prev.update(values)
                self.params[param] = prev
            self.loop = True  

    @staticmethod
    def from_json(obj):
        base = obj.get("base", "")
        urls = (APIUrl.from_json(url, base=base) for url in obj["urls"])
        return AllAPI(urls, ResultSaver(base=base))


# In[83]:

api = AllAPI.from_json({
    "base": "http://localhost:18080/api/v1/",
    "urls": [
        {"url": "applications", "provides": {"app-id": "id"}},
        {"url": ["applications/","{app-id}","/jobs"], "provides": {"job-id":"jobId"}},
        {"url": ["applications/","{app-id}","/stages"]},
        {"url": ["applications/","{app-id}","/jobs/","{job-id}"]},
]})

api.download()

