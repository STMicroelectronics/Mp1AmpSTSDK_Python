
CC ?= gcc
CFLAGS +=  -Wall -fPIC

LDFLAGS = -shared   # linking flags
RM = rm -f   # rm command
TARGET_LIB = libsdbsdk.so  # target lib

SRCS = sdbsdk.c  # source files
OBJS = $(SRCS:.c=.o)

.PHONY: all
all: ${TARGET_LIB}

$(TARGET_LIB): $(OBJS)
	$(CC) ${LDFLAGS} -o $@ $^

$(SRCS:.c):%.c
	$(CC) $(CFLAGS) $< >$@

include $(SRCS:.c)

.PHONY: clean
clean:
	-${RM} ${TARGET_LIB} ${OBJS} $(SRCS:.c)
