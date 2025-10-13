<template>
  <div class="graphs-view">
    <div class="dropdown-container">
      <q-select
        v-model="selectedChannel"
        :options="dropdownOptions1"
        label="Channel"
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
        label="Product"
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
        label="Time Frame"
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
        <div class="chart-title">Sales</div>
        <div ref="salesChartEl" class="chart-body"></div>
        <q-inner-loading :showing="isLoading">
          <q-spinner color="primary" size="42px" />
        </q-inner-loading>
      </div>
      <div class="chart-container">
        <div class="chart-title">GWP</div>
        <div ref="gwpChartEl" class="chart-body"></div>
        <q-inner-loading :showing="isLoading">
          <q-spinner color="primary" size="42px" />
        </q-inner-loading>
      </div>
    </div>

    <div class="charts-row">
      <div class="chart-container">
        <div class="chart-title">Total Attempts</div>
        <div ref="stackedBarChartEl" class="chart-body"></div>
        <q-inner-loading :showing="isLoading">
          <q-spinner color="primary" size="42px" />
        </q-inner-loading>
      </div>
    </div>

    <div class="charts-row">
      <div class="chart-container">
        <div class="chart-title">Type of Attempts</div>
        <q-table
          :rows="tableRows"
          :columns="tableColumns"
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
        <div class="chart-title">Conversion Rate</div>
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

import { useAxios } from '@/composables/axios'

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
  { label: 'Weekly', value: 'Weekly' },
  { label: 'Monthly', value: 'Monthly' },
  { label: 'Yearly', value: 'Yearly' }
]

const selectedChannel = ref(dropdownOptions1[0].value)
const selectedProduct = ref(dropdownOptions2[0].value)
const selectedDateType = ref(dropdownOptions3[0].value)

const isLoading = ref(false)
const loadError = ref('')
const reportData = ref([])

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

const tableColumns = [
  { name: 'date', label: 'Date', align: 'left', field: 'date' },
  { name: 'quoteCount', label: 'Quote Count', align: 'center', field: 'quoteCount' },
  { name: 'saleCount', label: 'Sale Count', align: 'center', field: 'saleCount' },
  { name: 'conversionRate', label: 'Conversion %', align: 'right', field: 'conversionRate' }
]

const tableRows = computed(() =>
  sortedReportData.value.map((item, index) => {
    const quoteCount = item.quote_count ?? 0
    const saleCount = item.sale_count ?? 0
    const conversionRate = quoteCount > 0 ? (saleCount / quoteCount) * 100 : 0

    return {
      id: item.id ?? index,
      date: dayjs(item.date_value).format('YYYY-MM-DD'),
      quoteCount,
      saleCount,
      conversionRate: `${conversionRate.toFixed(1)}%`
    }
  })
)

const fetchReportData = async () => {
  if (!selectedChannel.value || !selectedProduct.value || !selectedDateType.value) {
    return
  }

  isLoading.value = true
  loadError.value = ''

  try {
    const data = await $get('/api/v1/quotes/report_data', {
      params: {
        channel: selectedChannel.value,
        product: selectedProduct.value,
        date_type: selectedDateType.value
      }
    })

    reportData.value = Array.isArray(data) ? data : []
  } catch (err) {
    loadError.value =
      err?.response?.data?.detail ??
      err?.message ??
      'Unable to load report data'
    reportData.value = []
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
  const nonSalesSeries = data.map(item => {
    const quotes = item.quote_count ?? 0
    const sales = item.sale_count ?? 0
    return Math.max(quotes - sales, 0)
  })
  const conversionSeries = data.map(item => {
    const quotes = item.quote_count ?? 0
    const sales = item.sale_count ?? 0
    return quotes > 0 ? Number(((sales / quotes) * 100).toFixed(2)) : 0
  })

  const emptyState = categories.length === 0

  applyLineOption(salesChartInstance, {
    title: 'Sales',
    categories,
    seriesName: 'Sales',
    data: salesSeries,
    color: '#2E7D32',
    emptyState
  })

  applyLineOption(gwpChartInstance, {
    title: 'GWP',
    categories,
    seriesName: 'Quote Count',
    data: quoteSeries,
    color: '#0277BD',
    emptyState
  })

  applyStackedOption(stackedBarChartInstance, {
    title: 'Total Attempts',
    categories,
    sales: salesSeries,
    otherAttempts: nonSalesSeries,
    emptyState
  })

  applyLineOption(conversionChartInstance, {
    title: 'Conversion Rate',
    categories,
    seriesName: 'Conversion %',
    data: conversionSeries,
    color: '#6A1B9A',
    emptyState,
    yAxisLabelFormatter: value => `${value}%`,
    yAxisMax: 100
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
    grid: { left: 48, right: 16, bottom: 64, top: 48 },
    xAxis: {
      type: 'category',
      data: categories,
      name: 'Date',
      nameLocation: 'start',
      axisLabel: { rotate: 45 }
    },
    yAxis: {
      type: 'value',
      max: typeof yAxisMax === 'number' ? yAxisMax : undefined,
      axisLabel: yAxisLabelFormatter
        ? { formatter: value => yAxisLabelFormatter(value) }
        : undefined
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

const applyStackedOption = (instance, { title, categories, sales, otherAttempts, emptyState }) => {
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
      data: ['Sales', 'Other Attempts'],
      top: '40px',
      left: 'left'
    },
    grid: { left: 48, right: 16, bottom: 64, top: 100 },
    xAxis: {
      type: 'category',
      data: categories,
      name: 'Date',
      nameLocation: 'start',
      axisLabel: { rotate: 45 }
    },
    yAxis: {
      type: 'value'
    },
    series: [
      {
        name: 'Sales',
        type: 'bar',
        stack: 'attempts',
        data: sales,
        itemStyle: { color: '#2E7D32' }
      },
      {
        name: 'Other Attempts',
        type: 'bar',
        stack: 'attempts',
        data: otherAttempts,
        itemStyle: { color: '#FFB300' }
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

onMounted(() => {
  initCharts()
})

onBeforeUnmount(() => {
  disposeCharts()
})
</script>

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
