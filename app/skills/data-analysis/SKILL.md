---
name: data-analysis
description: Multi-step data analysis methodology. Covers data loading, cleaning, exploratory analysis, statistical modeling, and visualization. Used when the user asks to analyze data, find insights, or create data reports.
---

# Data Analysis Instructions

When asked to perform data analysis, follow these steps carefully:

## Step 1: Understand the Data
- Identify the data source, format, and structure
- Determine column types (numerical, categorical, datetime)
- Assess data quality: check for missing values, outliers, duplicates

## Step 2: Load and Clean
- Load the data using appropriate methods
- Handle missing values with imputation or removal as appropriate
- Normalize or standardize numerical features if needed
- Encode categorical variables

## Step 3: Exploratory Analysis
Use `load_skill_resource` to read `references/analysis-methods.md` for detailed guidance.
- Compute summary statistics (mean, median, std, quartiles)
- Identify correlations between variables
- Detect patterns and anomalies
- Create distribution visualizations

## Step 4: Statistical Modeling
- Select appropriate statistical tests based on data characteristics
- Test hypotheses with significance level α = 0.05
- Build regression models if relationships exist
- Validate model assumptions

## Step 5: Insights and Reporting
- Summarize key findings in plain language
- Rank insights by business impact
- Provide actionable recommendations
- Present confidence levels for each finding
