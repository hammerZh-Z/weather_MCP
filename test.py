def test(func):
    def wrapper():  
        print("test called with", func.__name__)
        return func()
    return wrapper
    

@test
def hello1():
    print("hello")

hello1()
