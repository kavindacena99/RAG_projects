const messageTimeFormatter = new Intl.DateTimeFormat(undefined, {
  hour: 'numeric',
  minute: '2-digit',
});

const sessionDateFormatter = new Intl.DateTimeFormat(undefined, {
  day: 'numeric',
  month: 'short',
});

export function formatMessageTimestamp(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '';
  }

  return messageTimeFormatter.format(date);
}

export function formatSessionTimestamp(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '';
  }

  const today = new Date();
  if (date.toDateString() === today.toDateString()) {
    return messageTimeFormatter.format(date);
  }

  return sessionDateFormatter.format(date);
}
