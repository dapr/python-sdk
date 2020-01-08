
def actormethodname(name):

    def methodname(funcobj):
        funcobj.__methodname__ = name
        return funcobj
    
    return methodname