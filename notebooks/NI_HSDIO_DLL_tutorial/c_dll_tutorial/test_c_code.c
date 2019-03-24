#include <stdio.h>
#include "test_c_header.h"

// #define EXPORT __declspec(dllexport)

EXPORT int test_function(){
    printf("DLL function: Hello World!");
}