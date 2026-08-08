"""Alternative GraphSAGE, GAT, GIN, and KPI-AA encoder definitions."""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import SAGEConv, GATConv, GINConv, GCNConv

class SAGEEncoder(torch.nn.Module):
    """Encode person nodes with two GraphSAGE message-passing layers.

    ``in_dim``, ``hidden``, and ``out`` define the feature and embedding widths;
    ``forward`` returns one embedding row per node and ignores ``edge_type`` for
    this homogeneous comparison arm.
    """

    def __init__(self, in_dim, hidden=32, out=32):
        super().__init__()
        self.conv1 = SAGEConv(in_dim, hidden)
        self.conv2 = SAGEConv(hidden, out)

    def forward(self, x, edge_index, edge_type=None):
        # edge_type is ignored for homogeneous GraphSAGE
        x = self.conv1(x, edge_index)
        x = F.relu(x)
        x = self.conv2(x, edge_index)
        return x

class GATEncoder(torch.nn.Module):
    """Encode person nodes with relation-collapsed graph attention layers.

    ``in_dim``, ``hidden``, ``out``, and ``heads`` configure the two attention
    layers; ``forward`` returns node embeddings and ignores ``edge_type``.
    """

    def __init__(self, in_dim, hidden=32, out=32, heads=2):
        super().__init__()
        # GAT outputs hidden * heads, so we adjust dims
        self.conv1 = GATConv(in_dim, hidden, heads=heads)
        self.conv2 = GATConv(hidden * heads, out, heads=1)

    def forward(self, x, edge_index, edge_type=None):
        # edge_type is ignored for standard GAT
        x = self.conv1(x, edge_index)
        x = F.relu(x)
        x = self.conv2(x, edge_index)
        return x

class _SAGE(torch.nn.Module):
    def __init__(self, in_dim, hidden=32, out=32, num_relations=None):
        super().__init__()
        self.enc = SAGEEncoder(in_dim, hidden, out)
        self.head = torch.nn.Linear(out, 1)
        
    def forward(self, x, edge_index, edge_type=None):
        z = self.enc(x, edge_index, edge_type)
        return self.head(z).squeeze(-1)

class _GAT(torch.nn.Module):
    def __init__(self, in_dim, hidden=32, out=32, num_relations=None):
        super().__init__()
        self.enc = GATEncoder(in_dim, hidden, out)
        self.head = torch.nn.Linear(out, 1)
        
    def forward(self, x, edge_index, edge_type=None):
        z = self.enc(x, edge_index, edge_type)
        return self.head(z).squeeze(-1)

class GINEncoder(torch.nn.Module):
    """Encode person nodes with graph isomorphism network layers.

    ``in_dim``, ``hidden``, and ``out`` define the MLP-backed convolution widths;
    ``forward`` returns a ``[num_nodes, out]`` embedding matrix and ignores
    ``edge_type``.
    """

    def __init__(self, in_dim, hidden=32, out=32):
        super().__init__()
        nn1 = nn.Sequential(nn.Linear(in_dim, hidden), nn.ReLU(), nn.Linear(hidden, hidden))
        self.conv1 = GINConv(nn1)
        nn2 = nn.Sequential(nn.Linear(hidden, hidden), nn.ReLU(), nn.Linear(hidden, out))
        self.conv2 = GINConv(nn2)

    def forward(self, x, edge_index, edge_type=None):
        x = self.conv1(x, edge_index)
        x = F.relu(x)
        x = self.conv2(x, edge_index)
        return x

class KPIAAEncoder(torch.nn.Module):
    """Approximate the KPI-AA comparison arm with two homogeneous graph-convolution layers.

    ``in_dim``, ``hidden``, and ``out`` configure the two ``GCNConv`` layers;
    ``forward`` returns homogeneous node embeddings and accepts ``edge_type``
    only for interface parity.
    """

    def __init__(self, in_dim, hidden=32, out=32):
        super().__init__()
        # Approximation of KPI-AA using GCN and combining local/global features
        self.conv1 = GCNConv(in_dim, hidden)
        self.conv2 = GCNConv(hidden, out)
        
    def forward(self, x, edge_index, edge_type=None):
        # In a full KPI-AA, this would fuse global edge betweenness and local similarity.
        # We approximate it here with standard GCN processing.
        x = self.conv1(x, edge_index)
        x = F.relu(x)
        x = self.conv2(x, edge_index)
        return x

class _GIN(torch.nn.Module):
    def __init__(self, in_dim, hidden=32, out=32, num_relations=None):
        super().__init__()
        self.enc = GINEncoder(in_dim, hidden, out)
        self.head = torch.nn.Linear(out, 1)
        
    def forward(self, x, edge_index, edge_type=None):
        z = self.enc(x, edge_index, edge_type)
        return self.head(z).squeeze(-1)

class _KPIAA(torch.nn.Module):
    def __init__(self, in_dim, hidden=32, out=32, num_relations=None):
        super().__init__()
        self.enc = KPIAAEncoder(in_dim, hidden, out)
        self.head = torch.nn.Linear(out, 1)
        
    def forward(self, x, edge_index, edge_type=None):
        z = self.enc(x, edge_index, edge_type)
        return self.head(z).squeeze(-1)
