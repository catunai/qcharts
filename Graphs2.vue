<template>
  <div class="graphs-view">
    <div class="dropdown-container">
      <q-select
        v-model="selectedChannel"
        :options="dropdownOptions1"
        :label="t('Channel')"
        outlined
        dense
        use-input
        input-placeholder="Channel"
        emit-value
        map-options
      />
      <q-select
        v-model="selectedProduct"
        :options="dropdownOptions2"
        :label="t('Product')"
        outlined
        dense
        use-input
        input-placeholder="Product"
        emit-value
        map-options
      />
      <q-select
        v-model="selectedDateType"
        :options="dropdownOptions3"
        :label="t('Time Frame')"
        outlined
        dense
        use-input
        input-placeholder="Time Frame"
        emit-value
        map-options
      />
    </div>

    <q-banner
      v-if="loadError"
      class="q-mt-md bg-red-1 text-negative"
      dense
    >
      {{ loadError }}
    </q-banner>

    <div class="charts-row">
      <div class="chart-container">
        <!-- <div class="chart-title">Sales</div> -->
        <div ref="salesChartEl" class="chart-body"></div>
        <q-inner-loading :showing="isLoading">
          <q-spinner color="primary" size="42px" />
        </q-inner-loading>
      </div>
      <div class="chart-container">
        <!-- <div class="chart-title">GWP</div> -->
        <div ref="gwpChartEl" class="chart-body"></div>
        <q-inner-loading :showing="isLoading">
          <q-spinner color="primary" size="42px" />
        </q-inner-loading>
      </div>
    </div>

    <div class="charts-row">
      <div class="chart-container">
        <!-- <div class="chart-title">Total Attempts</div> -->
        <div ref="stackedBarChartEl" class="chart-body"></div>
        <q-inner-loading :showing="isLoading">
          <q-spinner color="primary" size="42px" />
        </q-inner-loading>
      </div>
    </div>

    <div class="charts-row">
      <div class="chart-container">
        <div class="chart-title">{{ t('Type of Attempts') }}</div>
        <q-table
          :rows="tableRows"
          :columns="tableColumns"
          :pagination="{ rowsPerPage: 0 }"
          table-style="max-height: 300px"
          virtual-scroll
          :virtual-scroll-sticky-size-start="48"
          row-key="id"
          flat
          bordered
          dense
          :loading="isLoading"
          hide-bottom
          no-data-label="No data available"
        />
      </div>
      <div class="chart-container">
        <!-- <div class="chart-title">Success Rate</div> -->
        <div ref="conversionChartEl" class="chart-body"></div>
        <q-inner-loading :showing="isLoading">
          <q-spinner color="primary" size="42px" />
        </q-inner-loading>
      </div>
    </div>
  </div>
</template>

<script setup>
import * as echarts from 'echarts'
import dayjs from 'dayjs'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n';

import { useAxios } from '@/composables/axios'
import { laFontAwesomeAlt } from '@quasar/extras/line-awesome';

const { t } = useI18n({ inheritLocale: true, sync: true });
const { $get } = useAxios()

const dropdownOptions1 = [
  { label: 'Web', value: 'Web' },
  { label: 'Inbound', value: 'Inbound' },
  { label: 'All', value: 'All' }
]

const dropdownOptions2 = [
  { label: 'Commercial Auto', value: 'CommercialAuto' },
  { label: 'Commercial Property & Liability', value: 'CommercialBuildingGeneralLiability' },
  { label: 'All', value: 'All' }
]

const dropdownOptions3 = [
  { label: 'Weekly', value: 'week' },
  { label: 'Monthly', value: 'month' },
  { label: 'Yearly', value: 'year' }
]

const selectedChannel = ref(dropdownOptions1[0].value)
const selectedProduct = ref(dropdownOptions2[0].value)
const selectedDateType = ref(dropdownOptions3[0].value)

const isLoading = ref(false)
const loadError = ref('')
const reportData = ref([])
const meltedTableData = ref([])

const salesChartEl = ref(null)
const gwpChartEl = ref(null)
const stackedBarChartEl = ref(null)
const conversionChartEl = ref(null)

let salesChartInstance = null
let gwpChartInstance = null
let stackedBarChartInstance = null
let conversionChartInstance = null

const chartsReady = ref(false)

const sortedReportData = computed(() => {
  return [...reportData.value].sort(
    (a, b) => new Date(a.date_value).getTime() - new Date(b.date_value).getTime()
  )
})

// Dynamically generate tableColumns based on the last 5 dates from melted data
const tableColumns = computed(() => {
  if (!meltedTableData.value.length) {
    return [{ name: 'series', label: 'Series', align: 'left', field: 'series' }]
  }

  // Get unique dates sorted chronologically
  const uniqueDates = [...new Set(meltedTableData.value.map(item => item.date_value))]
    .sort((a, b) => new Date(a).getTime() - new Date(b).getTime())

  // Get last 5 dates
  const last5Dates = uniqueDates.slice(-5).map(dateValue => {
    const formattedDate = dayjs(dateValue).format('YYYY-MM-DD')
    return {
      name: formattedDate,
      label: formattedDate,
      align: 'center',
      field: formattedDate
    }
  })

  return [{ name: 'series', label: 'Series', align: 'left', field: 'series' }, ...last5Dates]
})

// Transform melted data into table rows
const tableRows = computed(() => {
  if (!meltedTableData.value.length) {
    return []
  }

  // Group data by series_name
  const groupedBySeries = meltedTableData.value.reduce((acc, item) => {
    if (!acc[item.series_name]) {
      acc[item.series_name] = {}
    }
    const dateKey = dayjs(item.date_value).format('YYYY-MM-DD')
    acc[item.series_name][dateKey] = item.series_value
    return acc
  }, {})

  // Define the order of series (matching the original order)
  const seriesOrder = [
    'Answering Machine - No Message',
    'Sale - Policy',
    'Call back scheduled',
    'Too expensive',
    'Inbound - extension',
    'No Reason Provided',
    'Purchased insurance elsewhere',
    'No Product Need',
    'Bad phone number',
    'Customer Policy not up for renewal',
    'Customer satisfied with current insurer',
    'Declined by Insurer for other reason',
    'Active Follow-up Present',
    'Other',
    'None',
    'Total'
  ]

  // Create table rows in the specified order
  return seriesOrder.map(seriesName => ({
    series: t(seriesName),
    ...groupedBySeries[seriesName] || {}
  }))
})

const fetchReportData = async () => {
  if (!selectedChannel.value || !selectedProduct.value || !selectedDateType.value) {
    return
  }

  isLoading.value = true
  loadError.value = ''

  try {
    // Fetch chart data (original endpoint)
    const data = await $get('/api/v1/quotes/report_data', {
      params: {
        channel: selectedChannel.value,
        product: selectedProduct.value,
        date_type: selectedDateType.value
      }
    })

    reportData.value = Array.isArray(data) ? data : []

    // Fetch melted table data (new endpoint)
    const meltedData = await $get('/api/v1/quotes/report_data_melted', {
      params: {
        channel: selectedChannel.value,
        product: selectedProduct.value,
        date_type: selectedDateType.value
      }
    })

    meltedTableData.value = Array.isArray(meltedData) ? meltedData : []
  } catch (err) {
    loadError.value =
      err?.response?.data?.detail ??
      err?.message ??
      'Unable to load report data'
    reportData.value = []
    meltedTableData.value = []
  } finally {
    isLoading.value = false
  }
}

const updateCharts = () => {
  if (!chartsReady.value) {
    return
  }

  const data = sortedReportData.value
  const categories = data.map(item => dayjs(item.date_value).format('YYYY-MM-DD'))
  const salesSeries = data.map(item => item.sale_count ?? 0)
  const quoteSeries = data.map(item => item.quote_count ?? 0)
  const sum_attempts = data.map(item => item.sum_attempts ?? 0)
  const newLeadsGiven = data.map(item => item.new_leads_given ?? 0)
  const newLeadsContacted = data.map(item => item.new_leads_contacted ?? 0)
  const leadsNoRecontactNeeded = data.map(item => item.leads_no_recontact_needed ?? 0)
  const leadsNoRecontactMade = data.map((item, index) => {
    const given = newLeadsGiven[index] ?? 0
    const contacted = newLeadsContacted[index] ?? 0
    const noRecontactNeeded = leadsNoRecontactNeeded[index] ?? 0
    return given - (contacted + noRecontactNeeded)
  })
  const nonSalesSeries = data.map(item => {
    const quotes = item.quote_count ?? 0
    const sales = item.sale_count ?? 0
    return Math.max(quotes - sales, 0)
  })
  const conversionSeries = data.map(item => {
    const leads = item.new_leads_contacted ?? 0
    const sales = item.sale_count ?? 0
    return leads > 0 ? Number(((sales / leads) * 100).toFixed(2)) : 0
  })

  const emptyState = categories.length === 0

  applyLineOption(salesChartInstance, {
    title: t('Sales'),
    categories,
    seriesName: t('Sales'),
    data: salesSeries,
    color: '#4CAF50',
    emptyState
  })

  applyLineOption(gwpChartInstance, {
    title: t('GWP'),
    categories,
    seriesName: t('GWP'),
    data: quoteSeries,
    color: '#2196F3',
    emptyState
  })

  applyStackedOption(stackedBarChartInstance, {
    title: t('Total Attempts'),
    categories,
    sumAttempts: sum_attempts,
    newLeadsGiven,
    newLeadsContacted,
    leadsNoRecontactNeeded,
    leadsNoRecontactMade,
    emptyState
  })

  applyLineOption(conversionChartInstance, {
    title: t('Success Rate'),
    categories,
    seriesName: t('Success %'),
    data: conversionSeries,
    color: '#9C27B0',
    emptyState,
    yAxisLabelFormatter: value => `${value}%`
  })
}

const applyLineOption = (instance, { title, categories, seriesName, data, color, emptyState, yAxisLabelFormatter, yAxisMax }) => {
  if (!instance) {
    return
  }

  instance.clear()

  if (emptyState) {
    instance.setOption({
      title: {
        text: title,
        left: 'left',
        textStyle: { color: 'green' }
      },
      xAxis: { type: 'category', data: [] },
      yAxis: { type: 'value' },
      graphic: [
        {
          type: 'text',
          left: 'center',
          top: 'middle',
          style: {
            text: 'No data available',
            fill: '#999',
            fontSize: 16
          }
        }
      ]
    })
    return
  }

  instance.setOption({
    title: {
      text: title,
      left: 'left',
      textStyle: { color: 'green' }
    },
    tooltip: {
      trigger: 'axis'
    },
    grid: { left: 32, right: 16, bottom: 16, top: 60, containLabel: true },
    xAxis: {
      type: 'category',
      data: categories,
      // name: 'Date',
      nameLocation: 'start',
      axisLabel: { rotate: 45 }
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false, lineStyle: { color: '#4a4a4a' } },
      axisTick: { show: false },
      max: typeof yAxisMax === 'number' ? yAxisMax : undefined,
      axisLabel: yAxisLabelFormatter
        ? { formatter: value => yAxisLabelFormatter(value) }
        : { color : '#4a4a4a' }
    },
    series: [
      {
        name: seriesName,
        type: 'line',
        data,
        smooth: true,
        lineStyle: { color },
        itemStyle: { color }
      }
    ]
  })
}

const applyStackedOption = (instance, { title, categories, sumAttempts, newLeadsGiven, newLeadsContacted, leadsNoRecontactNeeded, leadsNoRecontactMade, emptyState }) => {
  if (!instance) {
    return
  }

  instance.clear()

  if (emptyState) {
    instance.setOption({
      title: {
        text: title,
        left: 'left',
        textStyle: { color: 'green' }
      },
      xAxis: { type: 'category', data: [] },
      yAxis: { type: 'value' },
      graphic: [
        {
          type: 'text',
          left: 'center',
          top: 'middle',
          style: {
            text: 'No data available',
            fill: '#999',
            fontSize: 16
          }
        }
      ]
    })
    return
  }

  instance.setOption({
    title: {
      text: title,
      left: 'left',
      textStyle: { color: 'green' }
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' }
    },
    legend: {
      data: [t('Sum of Attempts'), t('New Leads Given'), t('New Leads Contacted'), t('Leads No Recontact Needed'), t('Leads No Recontact Made')],
      top: '40px',
      left: 'left'
    },
    grid: { left: 48, right: 16, bottom: 64, top: 100 },
    xAxis: {
      type: 'category',
      data: categories,
      // name: 'Date',
      nameLocation: 'start',
      axisLabel: { rotate: 45 }
    },
    yAxis: {
      type: 'value'
    },
    series: [
      {
        name: t('Sum of Attempts'),
        type: 'bar',
        stack: 'attempts',
        data: sumAttempts,
        itemStyle: { color: '#64B5F6' }
      },
      {
        name: t('New Leads Given'),
        type: 'bar',
        stack: 'attempts',
        data: newLeadsGiven,
        itemStyle: { color: '#BA68C8' }
      },
      {
        name: t('New Leads Contacted'),
        type: 'bar',
        stack: 'attempts',
        data: newLeadsContacted,
        itemStyle: { color: '#F06292' }
      },
      {
        name: t('Leads No Recontact Needed'),
        type: 'bar',
        stack: 'attempts',
        data: leadsNoRecontactNeeded,
        itemStyle: { color: '#FF7043' }
      },
      {
        name: t('Leads No Recontact Made'),
        type: 'bar',
        stack: 'attempts',
        data: leadsNoRecontactMade,
        itemStyle: { color: '#90CAF9' }
      }
    ]
  })
}

const resizeCharts = () => {
  salesChartInstance?.resize()
  gwpChartInstance?.resize()
  stackedBarChartInstance?.resize()
  conversionChartInstance?.resize()
}

const initCharts = () => {
  if (salesChartEl.value) {
    salesChartInstance = echarts.init(salesChartEl.value)
  }
  if (gwpChartEl.value) {
    gwpChartInstance = echarts.init(gwpChartEl.value)
  }
  if (stackedBarChartEl.value) {
    stackedBarChartInstance = echarts.init(stackedBarChartEl.value)
  }
  if (conversionChartEl.value) {
    conversionChartInstance = echarts.init(conversionChartEl.value)
  }

  window.addEventListener('resize', resizeCharts)
  chartsReady.value = true
  updateCharts()
}

const disposeCharts = () => {
  window.removeEventListener('resize', resizeCharts)

  salesChartInstance?.dispose()
  gwpChartInstance?.dispose()
  stackedBarChartInstance?.dispose()
  conversionChartInstance?.dispose()

  salesChartInstance = null
  gwpChartInstance = null
  stackedBarChartInstance = null
  conversionChartInstance = null
  chartsReady.value = false
}

watch(
  [selectedChannel, selectedProduct, selectedDateType],
  () => {
    fetchReportData()
  },
  { immediate: true }
)

watch(
  () => sortedReportData.value,
  () => {
    updateCharts()
  },
  { deep: true }
)

// Watch for locale changes and update charts
watch(
  () => t('Sales'), // Watching the locale indirectly through the translation function
  () => {
    updateCharts(); // Redraw charts when the locale changes
  }
);

onMounted(() => {
  initCharts()
})

onBeforeUnmount(() => {
  disposeCharts()
})
</script>

<i18n lang="json">
{
  "en": {
    "Channel": "Channel",
    "Product": "Product",
    "Time Frame": "Time Frame",
    "Sales": "Sales",
    "GWP": "GWP",
    "Total Attempts": "Total Attempts",
    "Type of Attempts": "Type of Attempts",
    "Latest Result": "Latest Result",
      "Answering Machine - No Message": "Answering Machine - No Message",
      "Call back scheduled": "Call back scheduled",
      "Declined by Insurer for other reason": "Declined by Insurer for other reason",
      "No Reason Provided": "No Reason Provided",
      "Purchased insurance elsewhere": "Purchased insurance elsewhere",
      "Other": "Other",
      "Sale - Policy": "Sale - Policy",
      "Sale - No recontact": "Sale - No recontact",
      "Too expensive": "Too expensive",
      "Inbound - extension": "Inbound - extension",
      "No Product Need": "No Product Need",
      "Bad phone number": "Bad phone number",
      "Customer Policy not up for renewal": "Customer Policy not up for renewal",
      "Customer satisfied with current insurer": "Customer satisfied with current insurer",
      "Active Follow-up Present": "Active Follow-up Present",
      "None": "None",
      "Total": "Total",
    "Success Rate": "Success Rate",
    "Success %": "Success %",
    "Sum of Attempts": "Sum of Attempts",
    "New Leads Given": "New Leads Given",
    "New Leads Contacted": "New Leads Contacted",
    "Leads No Recontact Needed": "Leads No Recontact Needed",
    "Leads No Recontact Made": "Leads No Recontact Made"
  },
  "fr": {
    "Channel": "Canal",
    "Product": "Produit",
    "Time Frame": "Période",
    "Sales": "Ventes",
    "GWP": "GWP",
    "Total Attempts": "Tentatives totales",
    "Type of Attempts": "Type de tentatives",
    "Latest Result": "Dernier résultat",
      "Answering Machine - No Message": "Répondeur - Pas de message",
      "Call back scheduled": "Date de rappel fixée",
      "Declined by Insurer for other reason": "Refusé par l'assureur pour autre raison",
      "No Reason Provided": "Raison non fournis",
      "Purchased insurance elsewhere": "Achat avec un compétiteur",
      "Other": "Autre",
      "Sale - Policy": "Vente - Police",
      "Sale - No recontact": "Vente - Ne pas recontacter",
      "Too expensive": "Trop coûteux",
      "Inbound - extension": "Entrant - extension",
      "No Product Need": "Produit non nécessaire",
      "Bad phone number": "Mauvais numéro de téléphone",
      "Customer Policy not up for renewal": "Police n'est pas dû pour le renouvellement",
      "Customer satisfied with current insurer": "Client satisfait avec l'assureur actuel",
      "Active Follow-up Present": "Suivi actif présent",
      "None": "Aucun",
      "Total": "Total",
    "Success Rate": "Taux de réussite",
    "Success %": "Taux de réussite",
    "Sum of Attempts": "Somme des tentatives",
    "New Leads Given": "Nouveaux prospects donnés",
    "New Leads Contacted": "Nouveaux prospects contactés",
    "Leads No Recontact Needed": "Prospects sans besoin de recontact",
    "Leads No Recontact Made": "Prospects sans recontact effectué"
  }
}
</i18n>

<style scoped>
.graphs-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.dropdown-container {
  display: flex;
  justify-content: flex-end;
  gap: 16px;
  flex-wrap: wrap;
}

.charts-row {
  display: flex;
  flex-direction: row;
  gap: 16px;
  flex-wrap: wrap;
}

.chart-container {
  flex: 1;
  min-width: 320px;
  min-height: 360px;
  background-color: #f9f9f9;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  padding: 16px;
  display: flex;
  flex-direction: column;
  position: relative;
}

.chart-title {
  font-family: 'TD Graphik';
  font-weight: 500;
  font-size: 18px;
  color: green;
  margin-bottom: 16px;
}

.chart-body {
  flex: 1;
}

.chart-body,
.chart-container {
  width: 100%;
}

.q-inner-loading {
  border-radius: 8px;
}
</style>
