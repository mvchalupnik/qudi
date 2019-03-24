class MyClass:

    print('This code is executed at import')
    class_var = 'This value can be accessed by MyClass.class_var even without any instances'

    def __init__(self):
        self.instance_var = 1

    def my_instance_method(self, value):
        self.instance_var = value

    def print_class_var(self):
        print(self.class_var)

    @classmethod
    def my_class_method(cls, value):
        cls.class_var = value

    @staticmethod
    def my_static_method():
        """
        static method doesn't use any of the instance or class variables.
        In principle, it can be defined outside of class.
        It makes sense to define it inside the class definition if the method is somehow logically bound to the class.
        """
        print('my_static_method was called')

