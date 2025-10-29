<template>
  <div class="report-view">
    <div class="dropdown-container">
      <q-btn
        label="Select Period"
        color="primary"
        outline
        icon="event"
        @click="openDateRangePicker"
      />
      <q-btn
        label="Chart Data"
        color="primary"
        outline
        @click="exportChartData"
      />
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
        <div class="table-header">
          <div class="chart-title">{{ t('Type of Attempts') }}</div>
          <q-select
            v-model="selectedTableOption"
            :options="tableDropdownOptions"
            :label="t('Attempt Number')"
            outlined
            dense
            use-input
            input-placeholder="Attempt Number"
            emit-value
            map-options
          />
        </div>
        <q-table
          :rows="tableRows"
          :columns="tableColumns"
          :pagination="{ rowsPerPage: 0 }"
          table-style="max-height: 300px"
          row-key="id"
          flat
          bordered
          dense
          :loading="isLoading"
          hide-bottom
          no-data-label="No data available"
        >
          <template #bottom-row>
            <q-tr class="totals-row">
              <q-td key="series" class="text-left">
                {{ tableRowTotals.series }}
              </q-td>
              <q-td
                v-for="col in periodColumns"
                :key="col.name"
                class="text-center"
              >
                {{ tableRowTotals[col.name] || 0 }}
              </q-td>
            </q-tr>
          </template>
        </q-table>
      </div>
      <div class="chart-container">
        <!-- <div class="chart-title">Success Rate</div> -->
        <div ref="conversionChartEl" class="chart-body"></div>
        <q-inner-loading :showing="isLoading">
          <q-spinner color="primary" size="42px" />
        </q-inner-loading>
      </div>
    </div>
    <div class="charts-row">
      <div class="chart-container">
        <div class="table-header">
          <div class="chart-title">{{ t('Leads Contacted by Advisor') }}</div>
        </div>
        <q-table
          :rows="advisorTableRows"
          :columns="advisorTableColumns"
          :pagination="{ rowsPerPage: 0 }"
          table-style="max-height: 300px"
          row-key="user_id"
          flat
          bordered
          dense
          :loading="isLoading"
          hide-bottom
          no-data-label="No data available"
        >
          <template #bottom-row>
            <q-tr class="totals-row">
              <q-td key="user_id" class="text-left">
                {{  advisorTableTotals.user_id }}
              </q-td>
              <q-td
                v-for="col in periodColumns"
                :key="col.name"
                class="text-center"
              >
                {{ advisorTableTotals[col.name] || 0 }}
              </q-td>
            </q-tr>
          </template>
        </q-table>
      </div>
    </div>
    
    <!-- Date Range Picker Dialog -->
    <q-dialog v-model="showDateRangePicker">
      <q-card style="min-width: 500px">
        <q-card-section>
          <div class="text-h6">Select Date Range</div>
        </q-card-section>
        
        <q-card-section class="q-pt-none">
          <div class="row q-col-gutter-md">
            <div class="col-6">
              <div class="text-subtitle2 q-mb-sm">Start Date</div>
              <q-date
                v-model="selectedStartDate"
                mask="YYYY-MM-DD"
                :options="date => new Date(date.replace(/\//g, '-')) <= new Date()"
              />
            </div>
            <div class="col-6">
              <div class="text-subtitle2 q-mb-sm">End Date</div>
              <q-date
                v-model="selectedEndDate"
                mask="YYYY-MM-DD"
                :options="date => new Date(date.replace(/\//g, '-')) <= new Date()"
              />
            </div>
          </div>
        </q-card-section>
        
        <q-card-actions align="right">
          <q-btn flat label="Cancel" color="primary" @click="cancelDateRange" />
          <q-btn flat label="OK" color="primary" @click="applyDateRange" />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </div>
</template>

<script setup>
import * as echarts from 'echarts'
import dayjs from 'dayjs'
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { useI18n } from 'vue-i18n';

import { useAxios } from '@/composables/axios'

const { t, locale } = useI18n({ inheritLocale: true, sync: true });
const { $get } = useAxios()

// Constants
const CHART_COLORS = {
  SALES: '#4CAF50',
  GWP: '#2196F3',
  SUCCESS_RATE: '#9C27B0',
  SUM_ATTEMPTS: '#64B5F6',
  NEW_LEADS_GIVEN: '#BA68C8',
  NEW_LEADS_CONTACTED: '#F06292',
  LEADS_NO_RECONTACT_NEEDED: '#FF7043',
  LEADS_NO_RECONTACT_MADE: '#90CAF9'
}

const SERIES_ORDER = [
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
  'None'
]

const RESIZE_DEBOUNCE_MS = 150

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

const tableDropdownOptions = [
  { label: '1', value: '1' },
  { label: '2', value: '2' },
  { label: '3', value: '3' },
  { label: 'All', value: 'All' },
]

const selectedChannel = ref(dropdownOptions1[0].value)
const selectedProduct = ref(dropdownOptions2[0].value)
const selectedDateType = ref(dropdownOptions3[0].value)
const selectedTableOption = ref('All')

// Date range state
const selectedStartDate = ref(null)
const selectedEndDate = ref(null)
const useDateRange = ref(false)
const showDateRangePicker = ref(false)

const isLoading = ref(false)
const loadError = ref('')
const reportData = shallowRef([])
const attemptTableData = shallowRef([])
const advisorTableData = shallowRef([])

const salesChartEl = ref(null)
const gwpChartEl = ref(null)
const stackedBarChartEl = ref(null)
const conversionChartEl = ref(null)

let salesChartInstance = null
let gwpChartInstance = null
let stackedBarChartInstance = null
let conversionChartInstance = null
let resizeDebounceTimer = null

const chartsReady = ref(false)

const sortedReportData = computed(() => {
  return [...reportData.value].sort(
    (a, b) => new Date(a.date_value).getTime() - new Date(b.date_value).getTime()
  )
})

// Filtered report data that matches the calculated period columns
const filteredReportData = computed(() => {
  // Get the list of period dates from periodColumns
  const periodDates = periodColumns.value.map(col => col.name)
  
  // Create a complete dataset with all periods
  return periodDates.map(dateStr => {
    // Look for existing data for this period
    const existingData = reportData.value.find(
      item => dayjs(item.date_value).format('YYYY-MM-DD') === dateStr
    )
    
    // If data exists, return it; otherwise create a record with zeros
    if (existingData) {
      return existingData
    } else {
      return {
        date_value: dateStr,
        date_type: selectedDateType.value,
        product: selectedProduct.value,
        quote_channel: selectedChannel.value,
        quote_count: 0,
        sale_count: 0,
        sum_attempts: 0,
        new_leads_given: 0,
        new_leads_contacted: 0,
        leads_no_recontact_needed: 0
      }
    }
  })
})

// Dynamically computed periods based on custom date range or last 5 dates
const periodColumns = computed(() => {
  const periods = []
  
  if (useDateRange.value && selectedStartDate.value && selectedEndDate.value) {
    // Custom date range mode
    let currentDate = dayjs(selectedStartDate.value)
    const endDate = dayjs(selectedEndDate.value)
    
    while (currentDate.isBefore(endDate) || currentDate.isSame(endDate, 'day')) {
      let periodEnd
      if (selectedDateType.value === 'week') {
        periodEnd = currentDate.endOf('week').subtract(1, 'day')
      } else if (selectedDateType.value === 'month') {
        periodEnd = currentDate.endOf('month')
      } else if (selectedDateType.value === 'year') {
        periodEnd = currentDate.endOf('year')
      }
      
      const formattedDate = periodEnd.format('YYYY-MM-DD')
      
      // Only add if we haven't already added this period and it's within range
      if (!periods.find(p => p.name === formattedDate) && (periodEnd.isBefore(endDate) || periodEnd.isSame(endDate, 'day'))) {
        periods.push({
          name: formattedDate,
          label: formattedDate,
          align: 'center',
          field: formattedDate
        })
      }
      
      // Move to next period
      currentDate = currentDate.add(1, selectedDateType.value)
    }
  } else {
    // Default mode - last 5 periods
    const now = dayjs()
    for (let i = 4; i >= 0; i--) {
      let periodDate
      if (selectedDateType.value === 'week') {
        periodDate = now.subtract(i, 'week').endOf('week').subtract(1, 'day')
      } else if (selectedDateType.value === 'month') {
        periodDate = now.subtract(i, 'month').endOf('month')
      } else if (selectedDateType.value === 'year') {
        periodDate = now.subtract(i, 'year').endOf('year')
      }
      const formattedDate = periodDate.format('YYYY-MM-DD')
      periods.push({
        name: formattedDate,
        label: formattedDate,
        align: 'center',
        field: formattedDate
      })
    }
    
    if (selectedDateType.value === 'year') {
      return periods.slice(-2) // For yearly, only show the last 2 periods
    }
  }
  
  return periods
})

const tableColumns = computed(() => {
  return [
    { name: 'series', label: t('Result'), align: 'left', field: 'series' },
    ...periodColumns.value,
  ]
})

const advisorTableColumns = computed(() => {
  return [
    { name: 'user_id', label: t('User Id'), align: 'left', field: 'user_id' },
    ...periodColumns.value,
  ]
})

// Transform melted data into table rows
const tableRows = computed(() => {
  if (!attemptTableData.value.length) {
    return []
  }

  // Group data by series_name
  const groupedBySeries = attemptTableData.value.reduce((acc, item) => {
    if (!acc[item.series_name]) {
      acc[item.series_name] = {}
    }
    const dateKey = dayjs(item.date_value).format('YYYY-MM-DD')
    acc[item.series_name][dateKey] = item.series_value
    return acc
  }, {})

  // Create table rows in the specified order
  return SERIES_ORDER.map(seriesName => ({
    series: t(seriesName),
    ...groupedBySeries[seriesName] || {}
  }))
})

// Transform advisor table data into rows excluding totals
const advisorTableRows = computed(() => {
  if (!advisorTableData.value.length) {
    return []
  }
  // Group data by user_id
  const groupedByUser = advisorTableData.value.reduce((acc, item) => {
    if (!acc[item.user_id]) {
      acc[item.user_id] = {}
    }
    const dateKey = dayjs(item.date_value).format('YYYY-MM-DD')
    acc[item.user_id][dateKey] = item.new_leads_contacted
    return acc
  }, {})

  // Transform grouped data into rows
  const rows = Object.keys(groupedByUser).map(userId => ({
    user_id: userId,
    ...groupedByUser[userId] // Spread the date values for this user
  }))

  // Filter out rows with no data
  const filteredRows = rows.filter(row => {
    return periodColumns.value.some(col => {
      const value = row[col.name]
      return value !== undefined && value !== null && value > 0
    })
  })

  return filteredRows
})

// Calculate totals for bottom-row slot
const advisorTableTotals = computed(() => {
  const totals = { user_id: t('Total') }

  periodColumns.value.forEach(col => {
    const sum = advisorTableRows.value.reduce((acc, row) => {
      const value = row[col.name]
      return acc + (value !== undefined && value !== null ? value : 0)
    }, 0)
    totals[col.name] = sum
  })

  return totals
})

// Calculate totals for Type of Attempts table
const tableRowTotals = computed(() => {
  const totals = { series: t('Total') }

  periodColumns.value.forEach(col => {
    const sum = tableRows.value.reduce((acc, row) => {
      const value = row[col.name]
      return acc + (value !== undefined && value !== null ? value : 0)
    }, 0)
    totals[col.name] = sum
  })

  return totals
}) 

// Consolidated data fetching
const fetchAllData = async () => {
  if (!selectedChannel.value || !selectedProduct.value || !selectedDateType.value) {
    return
  }

  isLoading.value = true
  loadError.value = ''

  try {
    // Fetch all data in parallel for better performance
    const [chartData, tableData, advisorData] = await Promise.all([
      $get('/api/v1/quotes/report_charts', {
        params: {
          channel: selectedChannel.value,
          product: selectedProduct.value,
          date_type: selectedDateType.value
        }
      }),
      $get('/api/v1/quotes/report_table', {
        params: {
          channel: selectedChannel.value,
          product: selectedProduct.value,
          date_type: selectedDateType.value,
          attempt_no: selectedTableOption.value
        }
      }),
      $get('/api/v1/quotes/report_advisor', {
        params: {
          channel: selectedChannel.value,
          product: selectedProduct.value,
          date_type: selectedDateType.value
        }
      })
    ])

    reportData.value = Array.isArray(chartData) ? chartData : []
    
    attemptTableData.value = Array.isArray(tableData)
      ? tableData.map(item => ({
          series_name: item.result,
          series_value: item.quote_count,
          date_value: item.date_value,
          date_type: item.date_type
        }))
      : []
    
    advisorTableData.value = Array.isArray(advisorData) ? advisorData : []
  } catch (err) {
    loadError.value =
      err?.response?.data?.detail ??
      err?.message ??
      'Unable to load data'
    reportData.value = []
    attemptTableData.value = []
    advisorTableData.value = []
  } finally {
    isLoading.value = false
  }
}

const fetchTableData = async () => {
  if (!selectedChannel.value || !selectedProduct.value || !selectedDateType.value) {
    return
  }

  isLoading.value = true
  loadError.value = ''

  try {
    const tableData = await $get('/api/v1/quotes/report_table', {
      params: {
        channel: selectedChannel.value,
        product: selectedProduct.value,
        date_type: selectedDateType.value
      }
    })

    attemptTableData.value = Array.isArray(tableData)
      ? tableData.map(item => ({
          series_name: item.result,
          series_value: item.quote_count,
          date_value: item.date_value
        }))
      : []
  } catch (err) {
    loadError.value =
      err?.response?.data?.detail ??
      err?.message ??
      'Unable to load table data'
    attemptTableData.value = []
  } finally {
    isLoading.value = false
  }
}

const updateCharts = () => {
  if (!chartsReady.value) {
    return
  }

  const data = filteredReportData.value
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
    color: CHART_COLORS.SALES,
    emptyState
  })

  applyLineOption(gwpChartInstance, {
    title: t('GWP'),
    categories,
    seriesName: t('GWP'),
    data: quoteSeries,
    color: CHART_COLORS.GWP,
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
    color: CHART_COLORS.SUCCESS_RATE,
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
        itemStyle: { color: CHART_COLORS.SUM_ATTEMPTS }
      },
      {
        name: t('New Leads Given'),
        type: 'bar',
        stack: 'attempts',
        data: newLeadsGiven,
        itemStyle: { color: CHART_COLORS.NEW_LEADS_GIVEN }
      },
      {
        name: t('New Leads Contacted'),
        type: 'bar',
        stack: 'attempts',
        data: newLeadsContacted,
        itemStyle: { color: CHART_COLORS.NEW_LEADS_CONTACTED }
      },
      {
        name: t('Leads No Recontact Needed'),
        type: 'bar',
        stack: 'attempts',
        data: leadsNoRecontactNeeded,
        itemStyle: { color: CHART_COLORS.LEADS_NO_RECONTACT_NEEDED }
      },
      {
        name: t('Leads No Recontact Made'),
        type: 'bar',
        stack: 'attempts',
        data: leadsNoRecontactMade,
        itemStyle: { color: CHART_COLORS.LEADS_NO_RECONTACT_MADE }
      }
    ]
  })
}

const debouncedResizeCharts = () => {
  if (resizeDebounceTimer) {
    clearTimeout(resizeDebounceTimer)
  }
  resizeDebounceTimer = setTimeout(() => {
    salesChartInstance?.resize()
    gwpChartInstance?.resize()
    stackedBarChartInstance?.resize()
    conversionChartInstance?.resize()
  }, RESIZE_DEBOUNCE_MS)
}

const initCharts = () => {
  try {
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

    window.addEventListener('resize', debouncedResizeCharts)
    chartsReady.value = true
    updateCharts()
  } catch (err) {
    console.error('Failed to initialize charts:', err)
    loadError.value = 'Failed to initialize charts'
  }
}

const disposeCharts = () => {
  if (resizeDebounceTimer) {
    clearTimeout(resizeDebounceTimer)
    resizeDebounceTimer = null
  }
  
  window.removeEventListener('resize', debouncedResizeCharts)

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

// Watch for filter changes and fetch all data
watch(
  [selectedChannel, selectedProduct, selectedDateType, selectedTableOption],
  () => {
    fetchAllData()
  },
  { immediate: true }
)

// Watch for data changes and update charts (shallow comparison)
watch(
  reportData,
  () => {
    updateCharts()
  }
)

// Watch for locale changes and update charts
watch(
  () => locale.value,
  () => {
    updateCharts()
  }
)

// Date range picker functions
const openDateRangePicker = () => {
  // Pre-fill with default dates if not already set
  if (!selectedStartDate.value || !selectedEndDate.value) {
    const now = dayjs()
    
    // Calculate start date (5 periods back)
    let startDate
    if (selectedDateType.value === 'week') {
      startDate = now.subtract(4, 'week').endOf('week').subtract(1, 'day')
    } else if (selectedDateType.value === 'month') {
      startDate = now.subtract(4, 'month').endOf('month')
    } else if (selectedDateType.value === 'year') {
      startDate = now.subtract(4, 'year').endOf('year')
    }
    
    // Calculate end date (current period end)
    let endDate
    if (selectedDateType.value === 'week') {
      endDate = now.endOf('week').subtract(1, 'day')
    } else if (selectedDateType.value === 'month') {
      endDate = now.endOf('month')
    } else if (selectedDateType.value === 'year') {
      endDate = now.endOf('year')
    }
    
    selectedStartDate.value = startDate.format('YYYY-MM-DD')
    selectedEndDate.value = endDate.format('YYYY-MM-DD')
  }
  
  showDateRangePicker.value = true
}

const applyDateRange = () => {
  if (selectedStartDate.value && selectedEndDate.value) {
    // Validate that start date is not after end date
    if (dayjs(selectedStartDate.value).isAfter(dayjs(selectedEndDate.value))) {
      // Show error - could use Quasar notify if available
      loadError.value = 'Start date must be before or equal to end date'
      return
    }
    
    useDateRange.value = true
    showDateRangePicker.value = false
    fetchAllData()
  }
}

const cancelDateRange = () => {
  showDateRangePicker.value = false
}

const exportChartData = () => {
  // Helper function to convert JSON data to CSV
  const convertToCSV = (data, headers) => {
    if (!data || data.length === 0) {
      return ''
    }

    // Create header row
    const headerRow = headers.join(',')
    
    // Create data rows
    const dataRows = data.map(row => {
      return headers.map(header => {
        let value = row[header]
        
        // Format dates
        if (value instanceof Date || (typeof value === 'string' && value.match(/^\d{4}-\d{2}-\d{2}/))) {
          value = dayjs(value).format('YYYY-MM-DD')
        }
        
        // Handle null/undefined
        if (value === null || value === undefined) {
          value = ''
        }
        
        // Escape special characters and wrap in quotes if needed
        value = String(value)
        if (value.includes(',') || value.includes('"') || value.includes('\n')) {
          value = `"${value.replace(/"/g, '""')}"`
        }
        
        return value
      }).join(',')
    }).join('\n')
    
    return `${headerRow}\n${dataRows}`
  }

  // Helper function to download CSV file
  const downloadCSV = (csvContent, filename) => {
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const link = document.createElement('a')
    const url = URL.createObjectURL(blob)
    
    link.setAttribute('href', url)
    link.setAttribute('download', filename)
    link.style.visibility = 'hidden'
    
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    
    URL.revokeObjectURL(url)
  }

  // Generate timestamp for filenames
  const timestamp = dayjs().format('YYYY-MM-DD_HH-mm-ss')

  // Export report_charts data
  if (reportData.value && reportData.value.length > 0) {
    const chartsHeaders = [
      'date_value',
      'date_type',
      'product',
      'quote_channel',
      'quote_count',
      'sale_count',
      'sum_attempts',
      'new_leads_given',
      'new_leads_contacted',
      'leads_no_recontact_needed'
    ]
    const chartsCSV = convertToCSV(reportData.value, chartsHeaders)
    downloadCSV(chartsCSV, `report_charts_${timestamp}.csv`)
  }

  // Export report_table data
  if (attemptTableData.value && attemptTableData.value.length > 0) {
    // Convert back to original API structure for export
    const tableDataForExport = attemptTableData.value.map(item => ({
      date_value: item.date_value,
      date_type: item.date_type,
      product: selectedProduct.value,
      quote_channel: selectedChannel.value,
      result: item.series_name,
      attempt_no: selectedTableOption.value,
      quote_count: item.series_value
    }))
    
    const tableHeaders = [
      'date_value',
      'date_type',
      'product',
      'quote_channel',
      'result',
      'attempt_no',
      'quote_count'
    ]
    const tableCSV = convertToCSV(tableDataForExport, tableHeaders)
    downloadCSV(tableCSV, `report_table_${timestamp}.csv`)
  }

  // Export report_advisor data
  if (advisorTableData.value && advisorTableData.value.length > 0) {
    const advisorHeaders = [
      'date_value',
      'date_type',
      'product',
      'quote_channel',
      'user_id',
      'new_leads_contacted'
    ]
    const advisorCSV = convertToCSV(advisorTableData.value, advisorHeaders)
    downloadCSV(advisorCSV, `report_advisor_${timestamp}.csv`)
  }

  // Show notification if no data available
  if (
    (!reportData.value || reportData.value.length === 0) &&
    (!attemptTableData.value || attemptTableData.value.length === 0) &&
    (!advisorTableData.value || advisorTableData.value.length === 0)
  ) {
    console.warn('No data available to export')
  }
}

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
    "Leads No Recontact Made": "Leads No Recontact Made",
    "Product": "Product",
        "CommercialAuto": "Commercial Auto",
        "CommercialBuildingGeneralLiability": "Commercial Property & Liability",
    "Leads Contacted by Advisor": "Leads Contacted by Advisor"
  },
  "fr": {
    "Channel": "Canal",
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
    "Leads No Recontact Made": "Prospects sans recontact effectué",
    "Product": "Produit",
        "CommercialAuto": "Auto commerciale",
        "CommercialBuildingGeneralLiability": "Assurance biens et responsabilité civile d'entreprise",
    "Leads Contacted by Advisor": "Prospects contactés par l'advisor"
  }
}
</i18n>

<style scoped>
.report-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.dropdown-container {
  display: flex;
  justify-content: flex-start;
  gap: 0;
  flex-wrap: wrap;
  align-items: center;
}

.dropdown-container .q-btn {
  margin-right: 8px;
}

.dropdown-container .q-select:first-of-type {
  margin-left: auto;
}

.dropdown-container .q-select:not(:first-of-type) {
  margin-left: 8px;
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

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.chart-title {
  font-family: 'TD Graphik';
  font-weight: 500;
  font-size: 18px;
  color: green;
  margin-bottom: 0;
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

:deep(.totals-row) {
  font-weight: 600;
  background-color: #f0f0f0;
}

:deep(.totals-row td) {
  font-weight: 600;
  border-top: 2px solid #c0c0c0;
}

:deep(.q-table thead tr th) {
  font-weight: 600;
  background-color: #f0f0f0;
  border-bottom: 2px solid #c0c0c0;
}

</style>
