export const groups:Record<string,string[]>={
 'Workspace':['Executive Overview','Inventory Dashboard','Replenishment Overview','Alerts and Notifications'],
 'Inventory Management':['Product Catalog','Stock Overview','Stock Movement','Warehouse Management','Inventory Transactions','Batch and Expiry Tracking'],
 'Predictive Analytics':['Demand Forecasting','Sales Trend Analysis','Product Demand Prediction','Seasonal Demand Analysis','Forecast Accuracy','Stockout Prediction','Overstock Risk Analysis'],
 'Replenishment Management':['Reorder Recommendations','Reorder Point Calculator','Safety Stock Calculator','Order Quantity Optimization','Replenishment Planning','Purchase Order Management','Replenishment History'],
 'Supplier Management':['Supplier Directory','Supplier Performance','Supplier Lead Time Analysis','Supplier Price Comparison','Supplier Risk Analysis'],
 'AI Agent Intelligence':['Agent Dashboard','Inventory Monitoring Agent','Demand Forecasting Agent','Replenishment Planning Agent','Supplier Analysis Agent','Purchase Order Agent','Inventory Optimization Agent','Risk Detection Agent','Orchestrator Agent','Agent Execution Logs'],
 'LLM Intelligence':['Inventory AI Assistant','Natural Language Inventory Analytics','Inventory Insights','Recommendation Explanations'],
 'Reports and Administration':['Inventory Reports','Forecast Reports','Supplier Reports','Purchase Order Reports','Data Import','User Management','System Settings','Audit Logs']
};
export const slug=(s:string)=>s.toLowerCase().replaceAll(' ','-');
