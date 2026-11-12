#!/usr/bin/env bash
# The manifests every harness reads, and what an installed copy carries.
#
# The version is carried by every file `scripts/bump.sh` moves, and only one of
# them is the one that matters: an installed copy updates when
# `.claude-plugin/plugin.json` says a new version exists. The others drift because nothing reads them at
# install time, so nothing complains.

set -euo pipefail
cd "${UIC_ROOT:-$(dirname "$0")/..}"

perl - <<'PERL'
use strict;
use warnings;
use JSON::PP;

sub raw { my ($f) = @_; open my $h, '<', $f or die "$f: $!\n"; local $/; my $t = <$h>; close $h; $t }
sub json { JSON::PP->new->utf8->decode(raw(shift)) }

my @fail;
my $plugin = json('.claude-plugin/plugin.json');
my $market = json('.claude-plugin/marketplace.json');
my ($entry) = grep { $_->{name} eq $plugin->{name} } @{ $market->{plugins} };
my @others = ('.codex-plugin/plugin.json', '.cursor-plugin/plugin.json', 'gemini-extension.json', 'plugin.json');

# The shipped version, the same everywhere.
my $version = $plugin->{version} // '';
push @fail, ".claude-plugin/plugin.json: version '$version' is not x.y.z" if $version !~ /^\d+\.\d+\.\d+$/;
push @fail, "marketplace.json: the entry carries " . ($entry->{version} // 'no version') . ", .claude-plugin/plugin.json $version"
  if ($entry->{version} // '') ne $version;
for my $file (@others) {
  my $v = json($file)->{version} // '';
  push @fail, "$file: version '$v', .claude-plugin/plugin.json $version" if $v ne $version;
}

# The plugin described the same way wherever it is listed: each place is read
# by a different harness's installer, and nothing reads more than one of them.
my $described = $plugin->{description} // '';
push @fail, "marketplace.json: the entry's description differs from .claude-plugin/plugin.json's" if ($entry->{description} // '') ne $described;
for my $file (@others, 'hooks/hooks.json') {
  push @fail, "$file: description differs from .claude-plugin/plugin.json's" if (json($file)->{description} // '') ne $described;
}

# One hook, at session start, through the wrapper that finds bash.
my $hooks = json('hooks/hooks.json')->{hooks};
my @events = sort keys %$hooks;
push @fail, "hooks/hooks.json: registers [@events]; only SessionStart" if "@events" ne 'SessionStart';
my $session = $hooks->{SessionStart}[0]{hooks}[0] // {};
push @fail, "hooks/hooks.json: SessionStart does not run run-hook.cmd session-start"
  if index($session->{command} // '', 'run-hook.cmd" session-start') < 0;
# Short on purpose: it prints a file, before anybody has asked for anything.
push @fail, "hooks/hooks.json: SessionStart timeout is over 5 seconds" if ($session->{timeout} // 99) > 5;
my $cursor = json('hooks/hooks-cursor.json')->{hooks}{sessionStart}[0]{command} // '';
push @fail, "hooks/hooks-cursor.json: sessionStart does not run run-hook.cmd session-start" if index($cursor, 'run-hook.cmd session-start') < 0;
for my $script ('hooks/run-hook.cmd', 'hooks/session-start') {
  push @fail, "$script: missing or not executable" unless -x $script;
}

# The licence LICENSE grants, in every manifest: each installer reads only its
# own, so a manifest without the field is a copy whose terms depend on which
# file was opened.
push @fail, "LICENSE: does not start 'MIT License'" if raw('LICENSE') !~ /\AMIT License/;
for my $file ('.claude-plugin/plugin.json', @others) {
  push @fail, "$file: licence is not MIT" if (json($file)->{license} // '') ne 'MIT';
}

# Copilot CLI reads plugin.json as a legacy plugin, which loads skills/ and
# hooks/hooks.json. The Agent Plugins $schema would move its hooks to
# com.github.copilot/hooks/, where there are none.
push @fail, "plugin.json: declares a \$schema; Copilot CLI would stop running the session hook"
  if exists json('plugin.json')->{'$schema'};

# Every harness pointed at the same skills.
for my $file ('.codex-plugin/plugin.json', '.cursor-plugin/plugin.json') {
  push @fail, "$file: skills is not ./skills/" if (json($file)->{skills} // '') ne './skills/';
}

# Codex reads a manifest's hooks entry instead of the plugin's hooks/hooks.json,
# so any entry, an empty one included, keeps the session hook from it. Without
# one, a package that leaves hooks/ out, as OpenAI's directory requires, stays
# valid.
push @fail, ".codex-plugin/plugin.json: has a hooks entry; Codex would not read hooks/hooks.json"
  if exists json('.codex-plugin/plugin.json')->{hooks};

# OpenAI's directory fills the listing from the Codex manifest's interface, and
# refuses a submission whose fields are missing or over its limits.
my $interface = json('.codex-plugin/plugin.json')->{interface} // {};
my %limit = (displayName => 30, shortDescription => 30, longDescription => 4000, developerName => 80);
for my $field (sort keys %limit) {
  my $value = $interface->{$field} // '';
  push @fail, ".codex-plugin/plugin.json: interface.$field is missing" if $value eq '';
  push @fail, ".codex-plugin/plugin.json: interface.$field is over $limit{$field} characters" if length $value > $limit{$field};
}
push @fail, ".codex-plugin/plugin.json: interface.category is missing" if ($interface->{category} // '') eq '';
my @capabilities = @{ $interface->{capabilities} // [] };
push @fail, ".codex-plugin/plugin.json: interface has over 20 capabilities" if @capabilities > 20;
push @fail, ".codex-plugin/plugin.json: an interface capability is over 120 characters" if grep { length > 120 } @capabilities;
my @prompts = @{ $interface->{defaultPrompt} // [] };
push @fail, ".codex-plugin/plugin.json: interface has over 3 starter prompts" if @prompts > 3;
push @fail, ".codex-plugin/plugin.json: an interface starter prompt is over 128 characters" if grep { length > 128 } @prompts;
for my $icon ('logo', 'composerIcon') {
  my $path = $interface->{$icon} // '';
  push @fail, ".codex-plugin/plugin.json: interface.$icon is not a file in the repository" unless $path =~ m{^\./} && -f $path;
}

# The context file the harnesses without a hook read: the one Gemini's
# manifest names, and every file it includes with a line `@./<path>`. Not
# AGENTS.md: that is where an agent working in this repository looks for the
# repository's own rules. It must carry the skills and the order they fire in.
my $first = json('gemini-extension.json')->{contextFileName} // '';
my @context = ($first);
my $first_text = raw($first);
push @context, $1 while $first_text =~ /^@\.\/(\S+)$/mg;
push @fail, "gemini-extension.json: loads AGENTS.md" if grep { $_ eq 'AGENTS.md' } @context;
push @fail, "gemini-extension.json: what it loads does not name ui-consistency:finding-patterns"
  if index(join("\n", map { raw($_) } @context), 'ui-consistency:finding-patterns') < 0;

# An installed copy is the repository's files alone. Claude Code runs
# `npm ci` in any copy that carries a package.json and a lockfile, and
# claude.ai's organisation sync rejects a top-level bin/.
for my $path ('package.json', 'package-lock.json', 'bin') {
  push @fail, "$path: an installed copy would carry it" if -e $path;
}
# A CLAUDE.md at the plugin root is not loaded as the plugin's context, and a
# strict validation fails on it. The instructions for working on the plugin
# live in .claude/CLAUDE.md, which Claude Code reads for this repository.
push @fail, "CLAUDE.md: at the plugin root, where a strict validation fails on it; keep it in .claude/" if -e 'CLAUDE.md';

if (@fail) {
  print STDERR "$_\n" for @fail;
  exit 1;
}
print "packaging: version $version and one description in every manifest; one hook; nothing to install\n";
PERL
