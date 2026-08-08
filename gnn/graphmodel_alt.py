"""Alternative GraphSAGE, GAT, GIN, and KPI-AA encoder definitions."""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import SAGEConv, GATConv, GINConv, GCNConv

class SAGEEncoder(torch.nn.Module):
    """Encode person nodes with two GraphSAGE message-passing layers.

    ``in_dim`` is the node-feature width, ``hidden`` is the first convolution's
    width, and ``out`` is the returned embedding width.  The module owns two
    ``SAGEConv`` layers and returns a ``[num_nodes, out]`` tensor from
    ``forward(x, edge_index, edge_type=None)``; ``edge_type`` is accepted only
    for a common encoder interface and is ignored.  Construction validates
    through PyTorch Geometric, has no filesystem side effects, and callers must
    supply a homogeneous edge index with feature rows aligned to its nodes.
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

    ``in_dim``, ``hidden``, and ``out`` control feature and embedding widths,
    while ``heads`` controls the first attention layer's heads.  ``forward``
    returns one embedding row per node and deliberately ignores ``edge_type``:
    this comparison arm receives a homogeneous ``edge_index`` and therefore
    cannot distinguish typed relations.  The module is in-memory only; PyG
    shape/type errors are caller-visible, and temporal edge eligibility must be
    enforced by the caller before scoring.
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

    ``in_dim``, ``hidden``, and ``out`` define the input and embedding widths.
    The two MLP-backed GIN convolutions return a ``[num_nodes, out]`` embedding
    matrix; ``edge_type`` is accepted for the shared arm interface but ignored.
    Construction has no artifact side effects and relies on PyG for tensor
    validation.  The caller remains responsible for passing only edges that
    were observable at the relevant as-of time.
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

    ``in_dim``, ``hidden``, and ``out`` set the node-feature and embedding widths.
    ``forward`` returns a ``[num_nodes, out]`` tensor from two ``GCNConv``
    layers; ``edge_type`` is accepted for API parity but is ignored, so this is
    an approximation rather than a typed KPI-AA implementation.  The module
    mutates only its PyTorch parameters during training, writes no artifacts,
    and requires the caller to provide an already filtered homogeneous graph.
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
