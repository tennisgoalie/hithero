<script lang="ts">
	import Alert from '$lib/components/Alert.svelte';
	import Button from '$lib/components/Button.svelte';
	import PageShell from '$lib/components/PageShell.svelte';
	import Seo from '$lib/components/Seo.svelte';
	import { apiFetch } from '$lib/api/client';
	import { routes } from '$lib/routes';
	import type { PageData } from './$types';
	import type { ValidationUser } from './+page.server';

	type StatusVariant = 'info' | 'success' | 'warning' | 'error';
	type StatusMessage = { variant: StatusVariant; message: string };
	type ValidationListResponse = {
		new_users: ValidationUser[];
		role: 'admin' | 'teacher';
	};

	let { data } = $props<{ data: PageData }>();

	const cardClass =
		'rounded-lg border border-slate-200 bg-white p-5 shadow-sm sm:flex sm:items-start sm:justify-between sm:gap-5';

	let users = $state<ValidationUser[]>([]);
	let role = $state<'admin' | 'teacher'>('teacher');
	let status = $state<StatusMessage | null>(null);
	let busyEmail = $state<string | null>(null);

	$effect(() => {
		users = data.new_users;
		role = data.role;
	});

	async function refreshList() {
		const body = await apiFetch<ValidationListResponse>('/api/validation_list/');
		users = body.new_users;
		role = body.role;
	}

	async function runUserAction(
		email: string,
		path: string,
		successMessage: string,
		shouldRefresh = true
	) {
		busyEmail = email;
		status = { variant: 'info', message: 'Updating validation list...' };

		try {
			await apiFetch<unknown>(path, { method: 'POST' });

			if (shouldRefresh) {
				await refreshList();
			}

			status = { variant: 'success', message: successMessage };
		} catch (error) {
			status = {
				variant: 'error',
				message: error instanceof Error ? error.message : 'The validation action failed.'
			};
		} finally {
			busyEmail = null;
		}
	}

	function validateUser(email: string) {
		void runUserAction(
			email,
			`/validation/validate_user/${encodeURIComponent(email)}`,
			`Validation successful for user: ${email}`
		);
	}

	function deleteUser(email: string) {
		if (
			!window.confirm(
				`Are you sure you want to delete user: ${email}? This action cannot be undone.`
			)
		) {
			return;
		}
		void runUserAction(
			email,
			`/validation/delete_user/${encodeURIComponent(email)}`,
			`Delete successful for user: ${email}`
		);
	}

	function reportUser(email: string) {
		if (!window.confirm(`Are you sure you want to report user: ${email}?`)) {
			return;
		}
		void runUserAction(
			email,
			`/validation/report_user/${encodeURIComponent(email)}`,
			`Report successful for user: ${email}`,
			false
		);
	}

	function emailUser(email: string) {
		void runUserAction(
			email,
			`/validation/emailed_user/${encodeURIComponent(email)}`,
			`Email status updated successfully for user: ${email}`
		);
	}

</script>

<Seo
	title="Validation - Homeroom Heroes"
	description="Validate educator signups for Homeroom Heroes."
	path={routes.validation}
	noindex
/>

<PageShell
	eyebrow="Validation"
	title="How Validation Works"
	intro="Review pending educator signups and school-change requests so every public teacher profile remains accurate."
>
	<div class="mx-auto max-w-4xl space-y-6">
		<noscript>
			<div class="rounded-md border border-amber-200 bg-amber-50 p-4 text-amber-950" role="alert">
				Validation, report, email, and delete actions require JavaScript. Reload this page with
				JavaScript enabled before using moderation controls.
			</div>
		</noscript>

		<section class="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
			<p class="text-base leading-7 text-slate-700">
				The validation process allows Homeroom Heroes to ensure only teachers are signing up. This
				way, donors know they are donating to teachers. If you know a pending teacher and can
				validate the information present, press the green Validate button. If you believe someone
				signed up with fake information, report the user and we will investigate.
			</p>
			</section>

			{#if status}
			<Alert variant={status.variant}>{status.message}</Alert>
		{/if}

		<section aria-labelledby="validation-list-heading">
			<h2 id="validation-list-heading" class="text-3xl font-bold tracking-normal text-green-800">
				Validation List
			</h2>

			<ul id="validationList" class="mt-5 space-y-4">
				{#each users as user (user.email)}
					<li class={cardClass}>
						<div class="space-y-2 text-slate-800">
							<p class="text-lg font-semibold">{user.name}</p>
							<p class="text-sm text-slate-600">{user.email}</p>
							<p class="text-sm leading-6 text-slate-700">
								{user.state} · {user.district} · {user.school} · {user.phone_number}
							</p>
						</div>

						<div class="mt-4 flex flex-wrap gap-2 sm:mt-0 sm:justify-end">
							<Button
								type="button"
								size="sm"
								disabled={busyEmail === user.email}
								onclick={() => validateUser(user.email)}
							>
								Validate
							</Button>

							{#if role === 'admin'}
								{#if user.emailed === 0}
									<Button
										type="button"
										size="sm"
										variant="secondary"
										disabled={busyEmail === user.email}
										onclick={() => emailUser(user.email)}
									>
										Emailed User
									</Button>
								{/if}
								<Button
									type="button"
									size="sm"
									variant="secondary"
									disabled={busyEmail === user.email}
									onclick={() => deleteUser(user.email)}
								>
									Delete
								</Button>
								{#if user.report === 1}
									<span class="self-center text-sm font-bold text-red-700">REPORTED</span>
								{/if}
							{:else}
								<Button
									type="button"
									size="sm"
									variant="secondary"
									disabled={busyEmail === user.email}
									onclick={() => reportUser(user.email)}
								>
									Report
								</Button>
							{/if}
						</div>
					</li>
				{/each}
			</ul>

			{#if users.length === 0}
				<p class="mt-5 rounded-lg border border-slate-200 bg-white p-8 text-center text-slate-700">
					No pending teachers need validation right now.
				</p>
			{/if}
		</section>
	</div>
</PageShell>
