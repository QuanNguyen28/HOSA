#!/usr/bin/env bash
# The skills' structure: what the platform requires of a skill, and that what a
# skill points at exists. Their wording is not checked — it changes as real work
# shows what to change, and real work is what checks it.
#
# Anthropic's limits for a skill, from its skill authoring best practices.

set -euo pipefail
cd "${UIC_ROOT:-$(dirname "$0")/..}"

perl - <<'PERL'
use strict;
use warnings;
use File::Basename qw(dirname);

sub slurp {
  my ($file) = @_;
  open my $h, '<:encoding(UTF-8)', $file or die "$file: $!\n";
  local $/;
  my $text = <$h>;
  close $h;
  return $text;
}

# A path with its `.` and `..` segments resolved, without touching the disk.
sub norm {
  my @out;
  for my $seg (split m{/}, shift) {
    next if $seg eq '.' || $seg eq '';
    if ($seg eq '..') { pop @out } else { push @out, $seg }
  }
  return join '/', @out;
}

my @fail;
opendir my $dir, 'skills' or die "skills/: $!\n";
my @skills = sort grep { !/^\./ && -d "skills/$_" } readdir $dir;
closedir $dir;

my @files;
for my $skill (@skills) {
  opendir my $d, "skills/$skill" or die;
  push @files, map { "skills/$skill/$_" } sort grep { /\.md$/ } readdir $d;
  closedir $d;
}

# Each skill, within the platform limits.
for my $skill (@skills) {
  my $file = "skills/$skill/SKILL.md";
  if (!-f $file) { push @fail, "$file: missing"; next }
  my $text = slurp($file);
  my (%field, $body);
  $body = $text;
  if ($text =~ /\A---\n(.*?)\n---\n?/s) {
    my $front = $1;
    $body = substr $text, length $&;
    for my $line (split /\n/, $front) {
      my $at = index $line, ':';
      next unless $at > 0;
      my ($field_name, $value) = (substr($line, 0, $at), substr($line, $at + 1));
      s/^\s+|\s+$//g for $field_name, $value;
      $field{$field_name} = $value;
    }
  }
  # Claude Code loads a skill whose front matter does not parse as YAML with no
  # fields set, and says nothing; Anthropic's directory blocks it. A plain value
  # carrying `: ` or ` #`, or starting with an indicator, is where that happens.
  for my $field_name (sort keys %field) {
    my $value = $field{$field_name};
    next if $value eq '' || $value =~ /^"(?:[^"\\]|\\.)*"$/ || $value =~ /^'(?:[^']|'')*'$/;
    push @fail, "$file: front matter '$field_name' is not valid YAML as written (': ' or ' #' in it, or an indicator first); quote it or reword it"
      if $value =~ /: | #|:$/ || $value =~ /^[\[\]{}>|*&!%@`'",?#]/ || $value =~ /^[-?:](?: |$)/;
  }
  my $name = $field{name} // '';
  push @fail, "$file: name '$name' is not its directory" if $name ne $skill;
  push @fail, "$file: name is not 1-64 lowercase letters, digits and hyphens" if $name !~ /^[a-z0-9-]{1,64}$/;
  push @fail, "$file: name contains 'anthropic' or 'claude'" if $name =~ /anthropic|claude/;

  my $description = $field{description} // '';
  push @fail, "$file: description is empty" if $description eq '';
  push @fail, "$file: description is " . length($description) . " characters, over 1,024" if length $description > 1024;
  push @fail, "$file: description carries an XML tag" if $description =~ /<[^>]+>/;
  push @fail, "$file: description does not say when to use it ('Use when')" if $description !~ /\bUse when\b/i;

  my $lines = () = split /\n/, $body, -1;
  push @fail, "$file: body is $lines lines, not under 500" if $lines >= 500;

  # After compaction Claude Code re-attaches only the first 5,000 tokens of a
  # skill (Claude Code's documentation on skills). 16,000 characters is 5,000
  # tokens at 3.2 characters a token, a low rate for English prose.
  push @fail, "$file: " . length($text) . " characters, over 16,000" if length $text > 16000;
}

# Every linked file exists, and every path to another skill's file written out.
for my $file (@files) {
  my $text = slurp($file);
  while ($text =~ /\]\(([^)#\s]+\.md)(?:#[^)]*)?\)|`(\.\.\/[^`\s]+\.md)`/g) {
    my $link = $1 // $2;
    next if $link =~ /^[a-z]+:/;
    push @fail, "$file: points at $link, which does not exist" unless -e dirname($file) . "/$link";
  }
}

# Every named section exists in the template that defines it. A section is
# named as `## <heading>` and defined inside a ````markdown template; a
# reference can wrap across lines, the heading cannot.
my %section;
for my $file (@files) {
  my $text = slurp($file);
  while ($text =~ /````markdown\n(.*?)\n````/gs) {
    my $block = $1;
    while ($block =~ /^## (.+)$/mg) { (my $heading = $1) =~ s/^\s+|\s+$//g; $section{$heading} = 1 }
  }
}
for my $file (@files) {
  my $text = slurp($file);
  while ($text =~ /`## ([^`]+)`/g) {
    (my $named = $1) =~ s/\s+/ /g;
    $named =~ s/^\s+|\s+$//g;
    push @fail, "$file: names '## $named', which no template defines" unless $section{$named};
  }
}

# Every skill named exists, and the session text names exactly these.
my %have = map { $_ => 1 } @skills;
for my $file (@files, 'USING.md') {
  my $text = slurp($file);
  while ($text =~ /\bui-consistency:([a-z][\w-]*)/g) {
    push @fail, "$file: names ui-consistency:$1, which does not exist" unless $have{$1};
  }
}
my %said;
my $session = slurp('hooks/session-context.md');
$said{$1} = 1 while $session =~ /\bui-consistency:([a-z][\w-]*)/g;
my ($said, $all) = (join(', ', sort keys %said), join(', ', @skills));
push @fail, "hooks/session-context.md names [$said]; the skills are [$all]" if $said ne $all;

# A link stays inside its own skill: a catalog's linter fails a skill whose link
# leaves it (the Agent Skills specification: paths from the skill root). Another
# skill's file is written out as a path instead.
# An invoked skill is re-attached after compaction; a file read with a tool is
# not. The skills a phase calls are reached by name, their own files included.
my %called = map { $_ => 1 } qw(values conventions decisions);
for my $file (@files) {
  my $from = (split m{/}, $file)[1];
  my $text = slurp($file);
  while ($text =~ /\]\(([^)#\s]+)(?:#[^)]*)?\)|`(\.\.\/[^`\s]+)`/g) {
    my ($link, $written) = ($1 // $2, defined $2);
    next if $link =~ /^[a-z]+:/;
    my $to = norm(dirname($file) . "/$link");
    next if $to =~ m{^skills/\Q$from\E/};
    my $into = $to =~ m{^skills/([^/]+)/} ? $1 : '';
    if ($called{$into}) { push @fail, "$file: points into $into ($link); name it as a skill to invoke" }
    elsif (!$written) { push @fail, "$file: links $link, outside its skill; write the path out" }
  }
}

# Skills and examples name roles, never one library's components: every
# technology builds a page differently. A denylist, because Markdown has no
# literals to isolate; a name nobody thought of is a missed catch, never a
# wrong one.
my @vendor = qw(
  Button TextField MenuItem DataGrid DataTable VirtualList Autocomplete
  DatePicker FormControl Chakra Drawer Popover Snackbar Alert Chip
  Modal IonButton IonPage mat-button v-btn react-hook-form formik yup zod
);
for my $file (@files, 'USING.md') {
  my $text = slurp($file);
  for my $name (@vendor) { push @fail, "$file: names the library component $name" if $text =~ /\b\Q$name\E\b/ }
}

if (@fail) {
  print STDERR "$_\n" for @fail;
  exit 1;
}
printf "skills: %d skills, %d files, all within the limits and pointing at what exists\n", scalar @skills, scalar @files;
PERL
