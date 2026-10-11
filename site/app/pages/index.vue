<template>
  <main class="wrap">
    <h1>Sweepstakes Casino Bonuses</h1>
    <p class="sub">Pulled from one public source - static build</p>

    <table v-if="casinos.length">
      <thead>
        <tr>
          <th>Casino</th>
          <th>Welcome bonus</th>
          <th>Wagering</th>
          <th>Min deposit</th>
          <th>Source</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="c in casinos" :key="c.casino">
          <td data-label="Casino">{{ c.casino }}</td>
          <td data-label="Welcome bonus">{{ c.welcome_bonus ?? '-' }}</td>
          <td data-label="Wagering">
            {{ c.wagering_requirement != null ? c.wagering_requirement + 'x' : '-' }}
          </td>
          <td data-label="Min deposit">{{ c.minimum_deposit ?? '-' }}</td>
          <td data-label="Source">
            <div class="src">
              <span class="src-original">{{ c.source_url.replace('https://', '') }}</span>
              <a
                v-if="c.archive_url"
                :href="c.archive_url"
                target="_blank"
                rel="noopener"
                class="src-archive"
              >View archived snapshot</a>
            </div>
          </td>
        </tr>
      </tbody>
    </table>

    <p v-else class="empty">No data.</p>

    <footer>
      <p>
        Data pulled from a public comparison page on covers.com. That source
        geo-restricts direct browser access from some regions, so the
        clickable link opens an Internet Archive snapshot of the same page.
      </p>
    </footer>
  </main>
</template>

<script setup lang="ts">
import bonuses from '~/data/bonuses.json'

type Casino = {
  casino: string
  welcome_bonus: string | null
  wagering_requirement: number | null
  minimum_deposit: string | null
  source_url: string
  archive_url: string | null
}

const casinos = bonuses as Casino[]
</script>