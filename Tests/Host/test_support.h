#ifndef TEST_SUPPORT_H
#define TEST_SUPPORT_H

#include <stdbool.h>

typedef struct
{
    unsigned int assertion_count;
    unsigned int failure_count;
} TestContext_t;

void Test_RecordAssertion(TestContext_t *context,
                          bool condition,
                          const char *expression,
                          const char *file,
                          int line);

#define TEST_EXPECT(context, expression)                                                   \
    Test_RecordAssertion((context), (expression), #expression, __FILE__, __LINE__)

#endif /* TEST_SUPPORT_H */
